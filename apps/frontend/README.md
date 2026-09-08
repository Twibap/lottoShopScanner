# Lotto Shop Scanner Web

기존 FastAPI 백엔드를 그대로 사용하는 반응형 웹 프런트엔드입니다. 빌드 도구나 런타임
프레임워크 없이 브라우저 표준 API로 구성되어 초기 로딩이 가볍고, 데스크톱과 모바일
브라우저에 모두 대응합니다.

## 기능

- 지역·주소·판매점명 검색
- 브라우저 현재 위치 검색
- 1/3/5/10km 반경 및 5가지 랭킹 정렬
- OpenStreetMap 타일 기반 지도 이동·확대·판매점 마커
- 판매점 당첨 통계, 전국 보조 순위, 당첨 이력 상세
- 로딩, 빈 결과, 오류 및 재시도 상태
- 검색 조건 URL 보존

## 실행

저장소 루트에서 전체 스택을 실행합니다.

```powershell
docker compose up --build postgres backend frontend
```

웹 주소는 `http://localhost:3000`, 기존 API 문서는 `http://localhost:8000/docs`입니다.

로컬 Node.js 개발 서버는 3000번 포트에서 `/api`를 `http://localhost:8000`으로
프록시합니다.

```powershell
node .\apps\frontend\dev-server.js
```

다른 백엔드를 사용할 때는 `API_PROXY_TARGET` 환경변수를 지정합니다.

## 검사

```powershell
node --check .\apps\frontend\app.js
node --check .\apps\frontend\map.js
node --test .\apps\frontend\test\*.test.js
docker compose config --quiet
```
