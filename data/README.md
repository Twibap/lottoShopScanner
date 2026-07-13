# 동행복권 당첨 판매점 수집

회차 하나만 전달하면 해당 회차만 조회합니다.

```powershell
python .\src\fetch_winning_shops.py 1232
```

시작 회차와 끝 회차를 함께 전달하면 두 회차를 모두 포함한 범위를 조회합니다.

```powershell
python .\src\fetch_winning_shops.py 1230 1232
```

기본 출력 파일은 `output/winning_shops.jsonl`입니다. 한 회차를 조회할 때마다
서버의 JSON 응답에 `draw` 필드를 더해 파일 끝에 한 줄로 즉시 추가합니다.
따라서 실행 도중 중단되어도 이미 저장된 회차는 유지됩니다.

이 파일은 각 줄이 독립적인 JSON 객체인 [JSON Lines](https://jsonlines.org/) 형식입니다.
같은 명령을 다시 실행하면 기존 내용을 덮어쓰지 않고 파일 끝에 계속 추가됩니다.

출력 경로를 바꾸려면 `--output` 옵션을 사용합니다.

```powershell
python .\src\fetch_winning_shops.py 1230 1232 --output .\output\winning_shops.jsonl
```

선택 옵션:

- `--delay`: 회차별 요청 간격(초), 기본값 `0.3`
- `--timeout`: 요청 제한 시간(초), 기본값 `30`
