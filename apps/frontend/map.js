const TILE_SIZE = 256;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function project(lat, lng, zoom) {
  const scale = TILE_SIZE * 2 ** zoom;
  const sin = Math.sin(lat * Math.PI / 180);
  return { x: (lng + 180) / 360 * scale, y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale };
}

function unproject(x, y, zoom) {
  const scale = TILE_SIZE * 2 ** zoom;
  const lng = x / scale * 360 - 180;
  const n = Math.PI - 2 * Math.PI * y / scale;
  return { lat: 180 / Math.PI * Math.atan(Math.sinh(n)), lng };
}

export class SlippyMap {
  constructor(element, { lat, lng, zoom = 14, onMove }) {
    this.el = element; this.center = { lat, lng }; this.zoom = zoom; this.onMove = onMove; this.shops = []; this.selected = null;
    this.tiles = element.querySelector('.map-tiles'); this.markers = element.querySelector('.map-markers');
    this.resize = new ResizeObserver(() => this.render()); this.resize.observe(element);
    this.bind(); this.render();
  }
  bind() {
    let drag = null;
    this.el.addEventListener('pointerdown', event => { if (event.target.closest('button,.marker,a')) return; drag = { x: event.clientX, y: event.clientY, center: project(this.center.lat, this.center.lng, this.zoom) }; this.el.setPointerCapture(event.pointerId); });
    this.el.addEventListener('pointermove', event => { if (!drag) return; const point = { x: drag.center.x - (event.clientX - drag.x), y: drag.center.y - (event.clientY - drag.y) }; this.center = unproject(point.x, point.y, this.zoom); this.render(); });
    this.el.addEventListener('pointerup', () => { if (drag) this.onMove?.(this.center); drag = null; });
    this.el.addEventListener('wheel', event => { event.preventDefault(); this.setZoom(this.zoom + (event.deltaY < 0 ? 1 : -1)); }, { passive: false });
    this.el.querySelector('[data-map-zoom="in"]').onclick = () => this.setZoom(this.zoom + 1);
    this.el.querySelector('[data-map-zoom="out"]').onclick = () => this.setZoom(this.zoom - 1);
  }
  setView(lat, lng, zoom = this.zoom) { this.center = { lat, lng }; this.zoom = clamp(zoom, 7, 18); this.render(); }
  setZoom(zoom) { this.zoom = clamp(zoom, 7, 18); this.render(); this.onMove?.(this.center); }
  setShops(shops, onSelect) { this.shops = shops; this.onSelect = onSelect; this.renderMarkers(); }
  render() { this.renderTiles(); this.renderMarkers(); }
  renderTiles() {
    const width = this.el.clientWidth, height = this.el.clientHeight;
    if (!width || !height) return;
    const center = project(this.center.lat, this.center.lng, this.zoom);
    const startX = Math.floor((center.x - width / 2) / TILE_SIZE), endX = Math.floor((center.x + width / 2) / TILE_SIZE);
    const startY = Math.floor((center.y - height / 2) / TILE_SIZE), endY = Math.floor((center.y + height / 2) / TILE_SIZE);
    const max = 2 ** this.zoom;
    const fragment = document.createDocumentFragment(); this.tiles.replaceChildren();
    for (let x = startX; x <= endX; x++) for (let y = startY; y <= endY; y++) {
      if (y < 0 || y >= max) continue;
      const img = new Image(); img.alt = ''; img.draggable = false;
      img.src = `https://tile.openstreetmap.org/${this.zoom}/${(x % max + max) % max}/${y}.png`;
      img.style.left = `${x * TILE_SIZE - center.x + width / 2}px`; img.style.top = `${y * TILE_SIZE - center.y + height / 2}px`; fragment.append(img);
    }
    this.tiles.append(fragment);
  }
  renderMarkers() {
    const width = this.el.clientWidth, height = this.el.clientHeight, center = project(this.center.lat, this.center.lng, this.zoom);
    const fragment = document.createDocumentFragment(), cells = new Map(); this.markers.replaceChildren();
    for (const shop of this.shops) {
      const point = project(shop.latitude, shop.longitude, this.zoom), left = point.x - center.x + width / 2, top = point.y - center.y + height / 2;
      if (left < -40 || left > width + 40 || top < -40 || top > height + 40) continue;
      const cellKey = this.zoom < 16 ? `${Math.round(left / 48)}:${Math.round(top / 48)}` : shop.shop_id;
      const cell = cells.get(cellKey) || { left, top, shops: [] }; cell.shops.push(shop); cells.set(cellKey, cell);
    }
    for (const cell of cells.values()) {
      const shop = cell.shops[0], clustered = cell.shops.length > 1;
      const button = document.createElement('button'); button.className = 'marker';
      button.style.left = `${cell.left}px`; button.style.top = `${cell.top}px`;
      if (clustered) button.classList.add('marker-cluster');
      button.textContent = clustered ? cell.shops.length : shop.result_rank;
      button.title = clustered ? `판매점 ${cell.shops.length}곳` : `${shop.result_rank}위 ${shop.name}`;
      button.onclick = () => clustered ? this.setView(shop.latitude, shop.longitude, this.zoom + 1) : this.onSelect?.(shop); fragment.append(button);
    }
    this.markers.append(fragment);
  }
}
