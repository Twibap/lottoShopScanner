import { SORTS, distanceLabel, escapeHtml, nearbyUrl, won } from './lib.js';
import { SlippyMap } from './map.js';

const DEFAULT = { lat: 37.5665, lng: 126.9780, radius: 3000, sort: 'distance', label: '서울시청 주변' };
const params = new URLSearchParams(location.search);
const state = {
  lat: Number(params.get('lat')) || DEFAULT.lat, lng: Number(params.get('lng')) || DEFAULT.lng,
  radius: Number(params.get('radius')) || DEFAULT.radius, sort: params.get('sort') || DEFAULT.sort,
  label: params.get('label') || DEFAULT.label, shops: [], mapCenter: null,
};

const $ = selector => document.querySelector(selector);
const results = $('#results'), count = $('#result-count'), label = $('#search-label');
const map = new SlippyMap($('#map'), { lat: state.lat, lng: state.lng, onMove: center => state.mapCenter = center });

function syncControls() {
  label.textContent = state.label; $('#radius').value = state.radius;
  $('#sorts').innerHTML = SORTS.map(([value, text]) => `<button class="sort-button ${state.sort === value ? 'active' : ''}" data-sort="${value}">${text}</button>`).join('');
}

async function api(url) {
  const response = await fetch(url, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(10000) });
  if (!response.ok) {
    let message = '정보를 불러오지 못했습니다.';
    try { message = (await response.json()).detail || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}

async function loadShops({ updateUrl = true } = {}) {
  results.innerHTML = '<div class="state"><div><div class="spinner"></div>판매점을 찾고 있어요.</div></div>'; count.textContent = '검색 중';
  try {
    const payload = await api(nearbyUrl(state)); state.shops = payload.items;
    count.textContent = `${state.shops.length}곳`; renderShops(); map.setShops(state.shops, openDetail);
    if (updateUrl) {
      const query = new URLSearchParams({ lat: state.lat, lng: state.lng, radius: state.radius, sort: state.sort, label: state.label });
      history.replaceState(null, '', `${location.pathname}?${query}`);
    }
  } catch (error) {
    count.textContent = '오류';
    results.innerHTML = `<div class="state"><div>판매점 정보를 불러오지 못했어요.<br><small>${escapeHtml(error.message)}</small><br><button class="retry">다시 시도</button></div></div>`;
    $('.retry').onclick = () => loadShops();
  }
}

function renderShops() {
  if (!state.shops.length) { results.innerHTML = '<div class="state"><div>이 반경에는 등록된 판매점이 없어요.<br><small>검색 반경을 넓혀 보세요.</small></div></div>'; return; }
  results.innerHTML = state.shops.map(shop => `<button class="shop-card" data-id="${escapeHtml(shop.shop_id)}">
    <span class="rank">${shop.result_rank}</span><span class="shop-copy"><strong>${escapeHtml(shop.name)}</strong><span>${escapeHtml(shop.address)}</span><small>1등 ${shop.first_count}회 · 2등 ${shop.second_count}회 · 최근 ${shop.last_winning_draw}회</small></span><span class="distance">${distanceLabel(shop.distance_m)}</span>
  </button>`).join('');
  results.querySelectorAll('.shop-card').forEach(button => button.onclick = () => openDetail(state.shops.find(shop => shop.shop_id === button.dataset.id)));
}

async function openDetail(shop) {
  if (!shop) return;
  const dialog = $('#detail-dialog'), content = $('#detail-content');
  content.innerHTML = '<div class="state" style="min-height:300px"><div><div class="spinner"></div>상세 정보를 불러오고 있어요.</div></div>'; dialog.showModal();
  try {
    const query = new URLSearchParams({ lat: state.lat, lng: state.lng, radius_m: state.radius, sort: state.sort });
    const detail = await api(`/api/v1/shops/${encodeURIComponent(shop.shop_id)}?${query}`);
    const stats = [['1등', `${detail.first_count}회`], ['2등', `${detail.second_count}회`], ['당첨 회차', `${detail.winning_draw_count}회`], ['최근 당첨', `${detail.last_winning_draw}회`], ['1등 당첨금', won(detail.first_prize)], ['누적 당첨금', won(detail.total_prize)]];
    content.innerHTML = `<article class="detail-body"><p class="eyebrow">SHOP DETAIL</p><h2>${escapeHtml(detail.name)}</h2><p class="address">${escapeHtml(detail.address)}${detail.phone ? `<br>${escapeHtml(detail.phone)}` : ''}</p>
      <div class="chips"><span class="chip">${distanceLabel(detail.distance_m)}</span><span class="chip">기준 ${detail.latest_draw}회</span>${detail.current_rank ? `<span class="chip">현재 반경 내 ${detail.current_rank}위</span>` : ''}</div>
      <a class="directions" href="https://map.naver.com/p/search/${encodeURIComponent(detail.address)}" target="_blank" rel="noreferrer">네이버 지도로 길찾기 ↗</a>
      <h3>당첨 통계</h3><div class="stats">${stats.map(([key,value]) => `<div class="stat"><small>${key}</small><strong>${value}</strong></div>`).join('')}</div>
      <h3>전국 보조 순위</h3><div class="rank-rows"><div><span>전국 1등 횟수 순위</span><strong>${detail.first_rank}위</strong></div><div><span>전국 2등 횟수 순위</span><strong>${detail.second_rank}위</strong></div><div><span>전국 당첨금 순위</span><strong>${detail.total_prize_rank}위</strong></div></div>
      <h3>당첨 이력</h3><div>${detail.winning_history.length ? detail.winning_history.map(item => `<div class="history-item"><span><strong>${item.draw}회 · ${item.prize_rank}등</strong><br><small>${escapeHtml(item.draw_date)} · ${escapeHtml(item.win_method || '구매 방식 정보 없음')}</small></span><strong>${won(item.prize_amount)}</strong></div>`).join('') : '<p class="address">당첨 이력이 없습니다.</p>'}</div>
      <p class="notice">과거 당첨 이력은 향후 당첨 확률을 보장하지 않습니다. 판매점·당첨 결과는 동행복권 공개 데이터 기반입니다.</p></article>`;
  } catch (error) { content.innerHTML = `<div class="state" style="min-height:300px"><div>${escapeHtml(error.message)}<br><button class="retry">다시 시도</button></div></div>`; content.querySelector('.retry').onclick = () => openDetail(shop); }
}

async function searchPlaces(query) {
  const box = $('#search-results'); box.hidden = false; box.innerHTML = '<div class="search-result">검색 중…</div>';
  try {
    const payload = await api(`/api/v1/places/search?q=${encodeURIComponent(query)}&limit=10`);
    box.innerHTML = payload.items.length ? payload.items.map((place, index) => `<button class="search-result" data-index="${index}"><strong>${escapeHtml(place.title)}</strong><small>${escapeHtml(place.address)}</small></button>`).join('') : '<div class="search-result">검색 결과가 없습니다.</div>';
    box.querySelectorAll('button').forEach(button => button.onclick = () => selectPlace(payload.items[Number(button.dataset.index)]));
  } catch (error) { box.innerHTML = `<div class="search-result">${escapeHtml(error.message)}</div>`; }
}

function selectPlace(place) {
  state.lat = place.latitude; state.lng = place.longitude; state.label = place.title; state.mapCenter = null;
  $('#search-results').hidden = true; $('#search-input').value = ''; map.setView(state.lat, state.lng, 15); syncControls(); loadShops();
}

function useLocation() {
  if (!window.isSecureContext) return toast('현재 위치는 HTTPS 주소에서만 사용할 수 있습니다.');
  if (!navigator.geolocation) return toast('이 브라우저에서는 위치를 사용할 수 없습니다.');
  $('#my-location').textContent = '위치 확인 중…';
  navigator.geolocation.getCurrentPosition(position => {
    state.lat = position.coords.latitude; state.lng = position.coords.longitude; state.label = '현재 위치 주변'; state.mapCenter = null;
    map.setView(state.lat, state.lng, 15); syncControls(); loadShops(); $('#my-location').innerHTML = '<span>◎</span> 현재 위치로 찾기'; toast('현재 위치를 기준으로 검색했습니다.');
  }, () => { $('#my-location').innerHTML = '<span>◎</span> 현재 위치로 찾기'; toast('위치 권한을 허용하거나 지역을 검색해 주세요.'); }, { enableHighAccuracy: true, timeout: 8000 });
}

let toastTimer;
function toast(message) { const element = $('#toast'); element.textContent = message; element.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => element.classList.remove('show'), 2800); }

$('#search-form').onsubmit = event => { event.preventDefault(); const query = $('#search-input').value.trim(); if (query.length < 2) return toast('검색어를 두 글자 이상 입력해 주세요.'); searchPlaces(query); };
$('#my-location').onclick = useLocation;
$('#radius').onchange = event => { state.radius = Number(event.target.value); loadShops(); };
$('#sorts').onclick = event => { const button = event.target.closest('[data-sort]'); if (!button) return; state.sort = button.dataset.sort; syncControls(); loadShops(); };
$('#search-center').onclick = () => { if (!state.mapCenter) return toast('지도를 먼저 움직여 주세요.'); state.lat = state.mapCenter.lat; state.lng = state.mapCenter.lng; state.label = '지도 중심 주변'; syncControls(); loadShops(); };
$('#results-handle').onclick = () => {
  const panel = document.querySelector('.results-panel');
  const collapsed = panel.classList.toggle('collapsed');
  document.body.classList.toggle('results-collapsed', collapsed);
  $('#results-handle').setAttribute('aria-expanded', String(!collapsed));
  $('#results-handle').setAttribute('aria-label', collapsed ? '판매점 목록 펼치기' : '판매점 목록 접기');
};
$('#open-info').onclick = () => $('#info-dialog').showModal();
document.querySelectorAll('.dialog-close').forEach(button => button.onclick = () => button.closest('dialog').close());
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); }));
document.addEventListener('click', event => { if (!event.target.closest('.search-panel')) $('#search-results').hidden = true; });

syncControls(); loadShops({ updateUrl: false });
