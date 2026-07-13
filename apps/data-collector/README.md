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

## 오류 코드

오류 로그의 `error_code`에는 다음 코드가 기록됩니다.

| 코드 | 의미 |
|---|---|
| `HTTP_<상태 코드>` | HTTP 요청 실패입니다. 예: `HTTP_408`, `HTTP_429`, `HTTP_500` |
| `TIMEOUT` | 설정한 요청 제한 시간을 초과했습니다. |
| `URL_ERROR` | DNS 조회 실패, 연결 거부 등 URL 요청 단계에서 오류가 발생했습니다. |
| `CONNECTION_ERROR` | 서버와의 연결이 끊기거나 연결 과정에서 오류가 발생했습니다. |
| `INVALID_JSON` | 서버 응답을 JSON으로 해석할 수 없습니다. |
| `INVALID_RESPONSE` | JSON이지만 예상한 `data` 객체가 없고 API 오류 코드도 없습니다. |
| `API_<resultCode>` | 동행복권 응답의 `resultCode`가 오류를 나타냅니다. 실제 값이 코드에 포함됩니다. |

HTTP 오류는 상태 코드가 그대로 포함되므로 `HTTP_400`부터 `HTTP_599`까지
수신한 실제 상태를 구분할 수 있습니다. HTTP `408`, `429`, `5xx`와
`TIMEOUT`, `URL_ERROR`, `CONNECTION_ERROR`, `INVALID_JSON`은 설정된 횟수만큼
재시도합니다. 그 밖의 HTTP `4xx`, `INVALID_RESPONSE`, `API_<resultCode>`는
즉시 실패로 기록됩니다.

## 로컬 테스트

자동 테스트는 `unittest.mock`으로 HTTP 요청을 대체하므로 동행복권 서버에 실제
요청을 보내지 않습니다. `data` 폴더에서 다음 명령으로 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

테스트 대상은 정상 응답, JSONL 저장과 이어받기, HTTP 429의 `Retry-After`,
HTTP 404, 타임아웃 재시도, 잘못된 JSON, API 오류 코드 및 건너뛰기 로그입니다.
