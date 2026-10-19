#!/usr/bin/env python3
"""Offline CLI for the same library used by the GUI."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rule_workbench.core import demo_project, run_checks
from rule_workbench.exports import import_json, export_bundle, export_json


def main():
    parser = argparse.ArgumentParser(description='규칙 검토 작업 실행 및 내보내기')
    parser.add_argument('--project', type=Path, help='GUI에서 내보낸 project.json')
    parser.add_argument('--demo', action='store_true', help='내장 예제 실행')
    parser.add_argument('--output', type=Path, required=True, help='새 ZIP 파일 경로')
    parser.add_argument('--include-data', action='store_true', help='선택한 원본 행과 문서 텍스트 포함')
    args = parser.parse_args()
    if bool(args.demo) == bool(args.project): parser.error('--demo 또는 --project 중 하나를 선택하세요.')
    project = demo_project() if args.demo else import_json(args.project.read_bytes())
    result = run_checks(project)
    with args.output.open('xb') as out: out.write(export_bundle(project, result, args.include_data))
    print(result['counts'])
    print(args.output.resolve())


if __name__ == '__main__': main()
