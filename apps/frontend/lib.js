export const SORTS = [
  ['distance', '가까운 순'], ['first_wins', '1등 당첨 순'], ['second_wins', '2등 당첨 순'],
  ['total_prize', '당첨금 순'], ['recent_win', '최근 당첨 순'],
];

export function distanceLabel(meters) {
  if (meters == null) return '거리 정보 없음';
  return meters < 1000 ? `${meters}m` : `${(meters / 1000).toFixed(1)}km`;
}

export function won(value) {
  return `${Number(value || 0).toLocaleString('ko-KR')}원`;
}

export function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
}

export function nearbyUrl({ lat, lng, radius, sort }) {
  const params = new URLSearchParams({ lat, lng, radius_m: radius, sort, limit: 100 });
  return `/api/v1/shops/nearby?${params}`;
}
