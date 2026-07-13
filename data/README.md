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
이미 파일에 저장된 회차는 자동으로 건너뛰므로 `Ctrl+C`로 중단한 뒤 같은 명령을
다시 실행하면 남은 회차부터 이어서 진행합니다.

진행 상황은 `[현재/남은 전체] 회차 조회 중...` 형태로 콘솔에 간단히 표시됩니다.
기본 로그 파일 `output/fetch_winning_shops.log`에는 시간, 로그 레벨, 저장 결과와
이미 완료되어 건너뛴 각 회차가 상세히 기록됩니다.

출력 경로를 바꾸려면 `--output` 옵션을 사용합니다.

```powershell
python .\src\fetch_winning_shops.py 1230 1232 --output .\output\winning_shops.jsonl
```

선택 옵션:

- `--delay`: 회차별 요청 간격(초), 기본값 `0.3`
- `--timeout`: 요청 제한 시간(초), 기본값 `30`
- `--log-file`: 로그 파일 경로, 기본값 `output/fetch_winning_shops.log`
- `--max-retries`: HTTP 408/429/5xx 또는 통신 오류의 재시도 횟수, 기본값 `5`
- `--max-backoff`: 재시도 시 최대 대기 시간(초), 기본값 `60`

서버가 `Retry-After` 헤더를 보내면 해당 시간을 우선 적용하고, 그렇지 않으면
재시도할 때마다 대기 시간을 늘립니다.
