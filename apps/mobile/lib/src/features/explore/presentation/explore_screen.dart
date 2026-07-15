import 'package:flutter/material.dart';
import 'package:flutter_naver_map/flutter_naver_map.dart';

import '../data/location_service.dart';
import '../data/shop_repository.dart';
import '../domain/shop.dart';
import 'shop_detail_screen.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({
    super.key,
    required this.repository,
    required this.mapEnabled,
    required this.locationService,
    this.supportEmail = '',
    this.onMapReady,
    this.onMarkersSynced,
  });

  final ShopRepository repository;
  final bool mapEnabled;
  final LocationService locationService;
  final String supportEmail;
  final ValueChanged<NaverMapController>? onMapReady;
  final VoidCallback? onMarkersSynced;

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  static const _radii = [1000, 3000, 5000, 10000];
  static const _fabSize = Size(112, 56);

  var _latitude = 37.5665;
  var _longitude = 126.9780;
  var _mapLatitude = 37.5665;
  var _mapLongitude = 126.9780;
  var _radiusM = 3000;
  var _sort = ShopSort.distance;
  var _loading = true;
  String _searchLabel = '서울시청 주변';
  String? _error;
  List<Shop> _shops = const [];
  NaverMapController? _mapController;
  var _mapLoaded = false;
  UserCoordinate? _currentLocation;
  Offset? _fabPosition;

  @override
  void initState() {
    super.initState();
    _initializeFromCurrentLocation();
  }

  Future<void> _initializeFromCurrentLocation() async {
    try {
      final coordinate = await widget.locationService.current();
      if (!mounted) return;
      setState(() {
        _currentLocation = coordinate;
        _latitude = coordinate.latitude;
        _longitude = coordinate.longitude;
        _mapLatitude = coordinate.latitude;
        _mapLongitude = coordinate.longitude;
        _searchLabel = '현재 위치 주변';
      });
      await _mapController?.updateCamera(
        NCameraUpdate.scrollAndZoomTo(
          target: NLatLng(coordinate.latitude, coordinate.longitude),
          zoom: 15,
        ),
      );
      _syncCurrentLocationOverlay();
    } on LocationException {
      // Keep the default Seoul City Hall coordinate when location is unavailable.
    } on Exception {
      // A location failure must not prevent the initial nearby-shop search.
    }
    await _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final shops = await widget.repository.nearby(
        latitude: _latitude,
        longitude: _longitude,
        radiusM: _radiusM,
        sort: _sort,
      );
      if (mounted) {
        setState(() => _shops = shops);
        await _syncMarkers();
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('HttpException: ', ''),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _syncMarkers() async {
    final controller = _mapController;
    if (controller == null || !_mapLoaded) return;
    await controller.clearOverlays(type: NOverlayType.marker);
    await controller.clearOverlays(type: NOverlayType.clusterableMarker);
    final markers = _shops.map((shop) {
      final marker = NClusterableMarker(
        id: shop.id,
        position: NLatLng(shop.latitude, shop.longitude),
        caption: NOverlayCaption(text: '${shop.resultRank}위 ${shop.name}'),
        iconTintColor: const Color(0xFF176B3A),
      );
      marker.setOnTapListener((_) {
        if (mounted) _openShopDetail(shop);
      });
      return marker;
    }).toSet();
    await controller.addOverlayAll(markers);
    widget.onMarkersSynced?.call();
  }

  Future<void> _moveToCurrentLocation() async {
    try {
      final coordinate = await widget.locationService.current();
      setState(() {
        _currentLocation = coordinate;
        _latitude = coordinate.latitude;
        _longitude = coordinate.longitude;
        _mapLatitude = coordinate.latitude;
        _mapLongitude = coordinate.longitude;
        _searchLabel = '현재 위치 주변';
      });
      await _mapController?.updateCamera(
        NCameraUpdate.scrollAndZoomTo(
          target: NLatLng(coordinate.latitude, coordinate.longitude),
          zoom: 15,
        ),
      );
      _syncCurrentLocationOverlay();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('현재 위치를 기준으로 검색했습니다.')));
      }
    } on LocationException catch (error) {
      if (mounted) await _showLocationFailure(error.failure);
    } on Exception {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('현재 위치를 확인하지 못했습니다.')));
      }
    }
  }

  Future<void> _showLocationFailure(LocationFailure failure) async {
    final serviceDisabled = failure == LocationFailure.serviceDisabled;
    final denied = failure == LocationFailure.denied;
    final permanentlyDenied = failure == LocationFailure.deniedForever;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(switch (failure) {
          LocationFailure.serviceDisabled => '위치 서비스가 꺼져 있습니다',
          LocationFailure.denied => '위치 권한이 허용되지 않았습니다',
          LocationFailure.deniedForever => '위치 권한이 차단되어 있습니다',
        }),
        content: Text(
          serviceDisabled
              ? '기기의 위치 서비스를 켜거나 지역을 직접 검색해 주세요.'
              : denied
              ? '권한 요청에서 허용을 선택하면 현재 위치 주변 판매점을 찾을 수 있습니다.'
              : '설정에서 위치 권한을 허용하거나 지역을 직접 검색해 주세요.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('취소'),
          ),
          if (serviceDisabled || permanentlyDenied)
            FilledButton(
              onPressed: () {
                Navigator.pop(context);
                if (serviceDisabled) {
                  widget.locationService.openLocationSettings();
                } else {
                  widget.locationService.openAppSettings();
                }
              },
              child: const Text('설정 열기'),
            ),
        ],
      ),
    );
  }

  Future<void> _searchMapCenter() async {
    setState(() {
      _latitude = _mapLatitude;
      _longitude = _mapLongitude;
      _searchLabel = '지도 중심 주변';
    });
    await _load();
  }

  Future<void> _openPlaceSearch() async {
    final place = await showModalBottomSheet<PlaceSearchResult>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => _PlaceSearchSheet(repository: widget.repository),
    );
    if (place == null) return;
    _latitude = place.latitude;
    _longitude = place.longitude;
    _mapLatitude = place.latitude;
    _mapLongitude = place.longitude;
    _searchLabel = place.title;
    await _mapController?.updateCamera(
      NCameraUpdate.scrollAndZoomTo(
        target: NLatLng(place.latitude, place.longitude),
        zoom: 15,
      ),
    );
    await _load();
  }

  Future<void> _captureMapCenter() async {
    final controller = _mapController;
    if (controller == null) return;
    final target = (await controller.getCameraPosition()).target;
    _mapLatitude = target.latitude;
    _mapLongitude = target.longitude;
  }

  void _syncCurrentLocationOverlay() {
    final controller = _mapController;
    final coordinate = _currentLocation;
    if (controller == null || coordinate == null) return;
    final overlay = controller.getLocationOverlay();
    overlay.setPosition(NLatLng(coordinate.latitude, coordinate.longitude));
    overlay.setIsVisible(true);
  }

  Future<void> _openResultsSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) {
          Future<void> reload() async {
            setSheetState(() {});
            await _load();
            if (context.mounted) setSheetState(() {});
          }

          return FractionallySizedBox(
            heightFactor: 0.82,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 4),
                  child: Text(
                    '주변 판매점',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                _Filters(
                  radiusM: _radiusM,
                  sort: _sort,
                  radii: _radii,
                  onRadiusChanged: (value) {
                    setState(() => _radiusM = value);
                    reload();
                  },
                  onSortChanged: (value) {
                    setState(() => _sort = value);
                    reload();
                  },
                ),
                Expanded(child: _buildResults()),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _openActionMenu() async {
    final action = await showModalBottomSheet<_ExploreAction>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.only(bottom: 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
                child: Row(
                  children: [
                    const Icon(Icons.place_outlined),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '탐색 메뉴',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          Text(
                            '현재 기준 · $_searchLabel',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              _ActionMenuTile(
                icon: Icons.search,
                title: '지역 검색',
                subtitle: '지역, 주소, 판매점명으로 찾기',
                action: _ExploreAction.search,
              ),
              _ActionMenuTile(
                icon: Icons.my_location,
                title: '현재 위치로 이동',
                subtitle: '내 위치 주변의 판매점 찾기',
                action: _ExploreAction.currentLocation,
              ),
              _ActionMenuTile(
                icon: Icons.list_alt,
                title: '주변 판매점',
                subtitle: _loading
                    ? '판매점을 검색하는 중입니다'
                    : '현재 반경 내 ${_shops.length}곳 · ${_sort.label}',
                action: _ExploreAction.results,
              ),
              _ActionMenuTile(
                icon: Icons.info_outline,
                title: '랭킹 기준 안내',
                subtitle: '순위 산정 기준과 데이터 안내',
                action: _ExploreAction.rankingInfo,
              ),
            ],
          ),
        ),
      ),
    );

    if (!mounted || action == null) return;
    switch (action) {
      case _ExploreAction.search:
        await _openPlaceSearch();
      case _ExploreAction.currentLocation:
        await _moveToCurrentLocation();
      case _ExploreAction.results:
        await _openResultsSheet();
      case _ExploreAction.rankingInfo:
        await showDialog<void>(
          context: context,
          builder: (context) => const _RankingNotice(),
        );
    }
  }

  void _openShopDetail(Shop shop) {
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (context) => ShopDetailScreen(
          repository: widget.repository,
          shop: shop,
          latitude: _latitude,
          longitude: _longitude,
          radiusM: _radiusM,
          sort: _sort,
          supportEmail: widget.supportEmail,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(
            child: _MapPanel(
              enabled: widget.mapEnabled,
              initialLatitude: _latitude,
              initialLongitude: _longitude,
              onMapReady: (controller) {
                _mapController = controller;
                widget.onMapReady?.call(controller);
                _syncCurrentLocationOverlay();
              },
              onMapLoaded: () {
                _mapLoaded = true;
                _syncMarkers();
              },
              onCameraIdle: _captureMapCenter,
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final maxX = constraints.maxWidth - _fabSize.width;
                  final maxY = constraints.maxHeight - _fabSize.height;
                  final position = Offset(
                    (_fabPosition?.dx ?? maxX).clamp(0.0, maxX),
                    (_fabPosition?.dy ?? maxY).clamp(0.0, maxY),
                  );
                  return Stack(
                    children: [
                      Align(
                        alignment: Alignment.topCenter,
                        child: FilledButton.tonalIcon(
                          onPressed: _loading ? null : _searchMapCenter,
                          icon: const Icon(Icons.refresh),
                          label: const Text('이 지역 다시 검색'),
                        ),
                      ),
                      Positioned(
                        left: position.dx,
                        top: position.dy,
                        width: _fabSize.width,
                        height: _fabSize.height,
                        child: GestureDetector(
                          onPanUpdate: (details) {
                            setState(() {
                              _fabPosition = Offset(
                                (position.dx + details.delta.dx).clamp(
                                  0.0,
                                  maxX,
                                ),
                                (position.dy + details.delta.dy).clamp(
                                  0.0,
                                  maxY,
                                ),
                              );
                            });
                          },
                          child: FloatingActionButton.extended(
                            heroTag: 'explore-menu',
                            tooltip: '탐색 메뉴',
                            onPressed: _openActionMenu,
                            icon: const Icon(Icons.menu),
                            label: Text(
                              _loading ? '검색 중' : '${_shops.length}곳',
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResults() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return _MessageState(
        icon: Icons.cloud_off_outlined,
        title: _error!,
        actionLabel: '다시 시도',
        onAction: _load,
      );
    }
    if (_shops.isEmpty) {
      return _MessageState(
        icon: Icons.location_off_outlined,
        title: '이 반경에는 판매점이 없습니다.',
        actionLabel: '반경 넓히기',
        onAction: () {
          setState(() => _radiusM = 10000);
          _load();
        },
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        itemCount: _shops.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                '$_searchLabel · 현재 반경 내 ${_shops.length}곳 · ${_sort.label}',
                style: Theme.of(context).textTheme.labelLarge,
              ),
            );
          }
          return _ShopCard(shop: _shops[index - 1], onTap: _openShopDetail);
        },
      ),
    );
  }
}

enum _ExploreAction { search, currentLocation, results, rankingInfo }

class _ActionMenuTile extends StatelessWidget {
  const _ActionMenuTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.action,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final _ExploreAction action;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: CircleAvatar(child: Icon(icon)),
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => Navigator.pop(context, action),
    );
  }
}

class _PlaceSearchSheet extends StatefulWidget {
  const _PlaceSearchSheet({required this.repository});

  final ShopRepository repository;

  @override
  State<_PlaceSearchSheet> createState() => _PlaceSearchSheetState();
}

class _PlaceSearchSheetState extends State<_PlaceSearchSheet> {
  final _controller = TextEditingController();
  var _loading = false;
  String? _error;
  List<PlaceSearchResult> _results = const [];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _controller.text.trim();
    if (query.length < 2) {
      setState(() {
        _error = '두 글자 이상 입력해 주세요.';
        _results = const [];
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await widget.repository.searchPlaces(query: query);
      if (mounted) setState(() => _results = results);
    } on Exception catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('HttpException: ', ''),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _controller,
            autofocus: true,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _search(),
            decoration: InputDecoration(
              hintText: '지역, 주소, 판매점명',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: IconButton(
                tooltip: '검색',
                onPressed: _search,
                icon: const Icon(Icons.arrow_forward),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(height: 360, child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return _MessageState(
        icon: Icons.search_off,
        title: _error!,
        actionLabel: '다시 검색',
        onAction: _search,
      );
    }
    if (_results.isEmpty) {
      return const Center(child: Text('검색어를 입력하면 지역, 주소, 판매점을 찾습니다.'));
    }
    return ListView.separated(
      itemCount: _results.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final result = _results[index];
        return ListTile(
          leading: const Icon(Icons.place_outlined),
          title: Text(
            result.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                result.address,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              Text(
                result.source == 'naver' ? 'NAVER 주소 검색' : '판매점 데이터',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ),
          onTap: () => Navigator.pop(context, result),
        );
      },
    );
  }
}

class _MapPanel extends StatelessWidget {
  const _MapPanel({
    required this.enabled,
    required this.initialLatitude,
    required this.initialLongitude,
    required this.onMapReady,
    required this.onMapLoaded,
    required this.onCameraIdle,
  });

  final bool enabled;
  final double initialLatitude;
  final double initialLongitude;
  final ValueChanged<NaverMapController> onMapReady;
  final VoidCallback onMapLoaded;
  final VoidCallback onCameraIdle;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: const Color(0xFFDDE9DF),
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (enabled)
            NaverMap(
              clusterOptions: NaverMapClusteringOptions(
                mergeStrategy: const NClusterMergeStrategy(
                  maxMergeableScreenDistance: 100,
                  willMergedScreenDistance: {
                    NInclusiveRange(0, 15): 100,
                    NInclusiveRange(16, 17): 65,
                    NInclusiveRange(18, 20): 35,
                  },
                ),
                clusterMarkerBuilder: (info, clusterMarker) {
                  clusterMarker.setIconTintColor(const Color(0xFF176B3A));
                  clusterMarker.setCaption(
                    NOverlayCaption(
                      text: '${info.size}',
                      color: Colors.white,
                      haloColor: const Color(0xFF176B3A),
                    ),
                  );
                },
              ),
              options: NaverMapViewOptions(
                initialCameraPosition: NCameraPosition(
                  target: NLatLng(initialLatitude, initialLongitude),
                  zoom: 14,
                ),
                locationButtonEnable: false,
                scaleBarEnable: false,
                contentPadding: EdgeInsets.zero,
              ),
              onMapReady: onMapReady,
              onMapLoaded: onMapLoaded,
              onCameraIdle: onCameraIdle,
            )
          else
            const Positioned.fill(
              child: Center(
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.map_outlined,
                        size: 54,
                        color: Color(0xFF6B8C73),
                      ),
                      SizedBox(height: 6),
                      Text(
                        'NAVER 지도 키를 설정하면 지도가 표시됩니다.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _Filters extends StatelessWidget {
  const _Filters({
    required this.radiusM,
    required this.sort,
    required this.radii,
    required this.onRadiusChanged,
    required this.onSortChanged,
  });

  final int radiusM;
  final ShopSort sort;
  final List<int> radii;
  final ValueChanged<int> onRadiusChanged;
  final ValueChanged<ShopSort> onSortChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        scrollDirection: Axis.horizontal,
        children: [
          DropdownMenu<int>(
            width: 112,
            initialSelection: radiusM,
            onSelected: (value) {
              if (value != null) onRadiusChanged(value);
            },
            dropdownMenuEntries: [
              for (final radius in radii)
                DropdownMenuEntry(value: radius, label: '${radius ~/ 1000}km'),
            ],
          ),
          const SizedBox(width: 8),
          for (final option in ShopSort.values) ...[
            ChoiceChip(
              label: Text(option.label),
              selected: option == sort,
              onSelected: (_) => onSortChanged(option),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class _ShopCard extends StatelessWidget {
  const _ShopCard({required this.shop, required this.onTap});

  final Shop shop;
  final ValueChanged<Shop> onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.all(14),
        leading: CircleAvatar(child: Text('${shop.resultRank}')),
        title: Text(shop.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(shop.address, maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 5),
              Text(
                '1등 ${shop.firstCount}회 · 2등 ${shop.secondCount}회 · 최근 ${shop.lastWinningDraw}회',
              ),
            ],
          ),
        ),
        trailing: Text(shop.distanceLabel),
        onTap: () => onTap(shop),
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.actionLabel,
    required this.onAction,
  });

  final IconData icon;
  final String title;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 48),
          const SizedBox(height: 12),
          Text(title),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onAction, child: Text(actionLabel)),
        ],
      ),
    );
  }
}

class _RankingNotice extends StatelessWidget {
  const _RankingNotice();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('랭킹 기준'),
      content: const Text(
        '현재 검색 반경 안의 판매점만 비교합니다. 과거 당첨 이력은 향후 당첨 확률을 보장하지 않습니다.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('확인'),
        ),
      ],
    );
  }
}
