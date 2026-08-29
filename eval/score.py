"""轨迹评分脚本:离线确定性评估 AI-DM 核心轨迹。

用法:
    python eval/score.py                 # 全量评估
    python eval/score.py --trajectory tr-04

原理:
- 用真实 gameplay / providers 层(mock provider)按 evalset.json 逐条回放轨迹;
- 对每一步做断言(场景推进、统计数值、消息类型、守卫拦截);
- 输出人类可读报告 eval/report.txt 与结构化的 eval/report.json。
骰子结果用固定 seed 注入,保证可复现(确定性评测)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.dice as dice_mod  # noqa: E402
from app import persistence, safety  # noqa: E402
from app.gameplay import apply_command, start_session  # noqa: E402
from app.safety import InputValidationError  # noqa: E402


def _seeded_roll(expr: str, seed: int | None = None):
    return dice_mod.roll_expression(expr, seed=42 if seed is None else seed)


class Runner:
    def __init__(self) -> None:
        self.session = None
        self.passed = 0
        self.failed = 0
        self.notes: list[str] = []

    def _start(self, player: str):
        self.session = start_session(persistence.new_id(), player_name=player)

    def _check(self, cond: bool, note: str):
        if cond:
            self.passed += 1
            self.notes.append(f"  [ok] {note}")
        else:
            self.failed += 1
            self.notes.append(f"  [FAIL] {note}")

    def run_step(self, step: dict) -> None:
        typ = step["type"]
        if typ == "setup":
            self._start(step.get("player", "无名调查员"))
            self._check(
                self.session.state.scene_id == step.get("expect_scene", "prologue"),
                f"setup: 场景 {self.session.state.scene_id}",
            )
            return
        if typ == "command":
            text = step["text"]
            if apply_command(self.session, text) is None:
                self._check(False, f"命令未识别: {text}")
                return
            msgs = self.session.messages
            if step.get("expect") == "roll_msg":
                self._check(any(m.kind == "roll" for m in msgs), "产生 roll 消息")
            elif step.get("expect") == "check_msg":
                self._check(any(m.kind == "check" for m in msgs), "产生 check 消息")
                if step.get("check_has"):
                    # DC 在 check 消息,成功/失败等程度词在随后的叙述里,取最近 4 条合并校验
                    window = "\n".join(m.content or "" for m in self.session.messages[-4:])
                    self._check(all(k in window for k in step["check_has"]), f"检定窗口包含 {step['check_has']}")
                if step.get("check_any_of"):
                    window = "\n".join(m.content or "" for m in self.session.messages[-4:])
                    self._check(any(k in window for k in step["check_any_of"]), f"检定窗口至少包含 {step['check_any_of']}")
            if step.get("stats_rolls_gte") is not None:
                self._check(self.session.stats["rolls"] >= step["stats_rolls_gte"], "掷骰统计达标")
            if step.get("stats_checks_eq") is not None:
                self._check(self.session.stats["checks"] == step["stats_checks_eq"], "检定统计等于期望")
            return
        if typ == "free":
            text = step["text"]
            old_roll = dice_mod.roll_expression
            dice_mod.roll_expression = _seeded_roll
            try:
                import asyncio

                from app.providers import propose_or_resolve

                asyncio.run(propose_or_resolve(self.session, text))
            finally:
                dice_mod.roll_expression = old_roll
            exp = step.get("expect_scene")
            if exp:
                self._check(self.session.state.scene_id == exp, f"free: 推进到 {self.session.state.scene_id}(期望 {exp})")
            return
        if typ == "free_guarded":
            text = step["text"]
            guard = safety.scan_guardrails(text)
            if guard:
                self._check(True, "守卫拦截命中(角色内化解)")
            else:
                self._check(False, "守卫未命中")
            return
        if typ == "bad_input":
            try:
                safety.sanitize_input(step["text"])
                self._check(False, "应拒绝超长输入")
            except InputValidationError:
                self._check(True, "超长输入被拒绝")
            return
        if typ == "assert":
            if step.get("kind") == "greeting":
                texts = "".join(m.content or "" for m in self.session.messages)
                self._check(all(k in texts for k in step["must_contain"]), f"开场包含 {step['must_contain']}")
            elif step.get("kind") == "system_msg":
                self._check(sum(1 for m in self.session.messages if m.kind == "system") >= step.get("count_gte", 1), "存在系统消息")
            elif step.get("kind") == "check_meta":
                checks = [m for m in self.session.messages if m.kind == "check"]
                if not checks:
                    self._check(False, "没有 check 消息可校验 meta")
                else:
                    meta = checks[-1].meta or {}
                    deg_ok = step.get("has_degree", False) and meta.get("degree") in ("大成功", "成功", "失败", "大失败")
                    dc_ok = step.get("has_dc", False) and isinstance(meta.get("dc"), int)
                    self._check(deg_ok and dc_ok, f"结构化 meta 检定裁决有效 (degree={meta.get('degree')}, dc={meta.get('dc')})")
            elif step.get("kind") == "events":
                evs = "".join(self.session.state.events)
                self._check(all(k in evs for k in step["must_contain"]), f"大事记包含 {step['must_contain']}")
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-DM 轨迹评分")
    parser.add_argument("--trajectory", "-t", default=None, help="只运行指定轨迹 id")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()

    evalset = json.loads((ROOT / "eval" / "evalset.json").read_text(encoding="utf-8"))
    trajectories = evalset["trajectories"]
    if args.trajectory:
        trajectories = [t for t in trajectories if t["id"] == args.trajectory]
    if not trajectories:
        print(f"未找到轨迹: {args.trajectory}", file=sys.stderr)
        return 2

    results = []
    grand_notes: list[str] = []
    for traj in trajectories:
        runner = Runner()
        for step in traj["steps"]:
            try:
                runner.run_step(step)
            except Exception as exc:  # 防御性:单步异常记失败不中断
                runner.failed += 1
                runner.notes.append(f"  [FAIL] 步执行异常: {exc!r}")
        passed, failed = runner.passed, runner.failed
        status = "PASS" if failed == 0 else "PARTIAL"
        results.append({"id": traj["id"], "name": traj["name"], "passed": passed, "failed": failed, "status": status})
        grand_notes.append(f"== {traj['id']} {traj['name']} [{status}] ==")
        grand_notes.extend(runner.notes)
        grand_notes.append("")

    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total = total_passed + total_failed
    rate = (total_passed / total * 100) if total else 0.0

    report = "\n".join(grand_notes)
    summary = (
        f"轨迹 {len(trajectories)} 条;断言 {total_passed}/{total} 通过,失败 {total_failed};通过率 {rate:.1f}%\n"
    )
    payload = {
        "total_trajectories": len(trajectories),
        "passed_assertions": total_passed,
        "failed_assertions": total_failed,
        "pass_rate": round(rate, 1),
        "results": results,
    }

    (ROOT / "eval" / "report.txt").write_text(summary + "\n" + report, encoding="utf-8")
    (ROOT / "eval" / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(summary)
        print("\n".join(grand_notes))
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
