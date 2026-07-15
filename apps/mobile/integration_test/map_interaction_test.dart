import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_naver_map/flutter_naver_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/location_service.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/shop_repository.dart';
import 'package:lotto_shop_scanner/src/features/explore/domain/shop.dart';
import 'package:lotto_shop_scanner/src/features/explore/presentation/explore_screen.dart';

const _clientId = String.fromEnvironment('NAVER_MAP_CLIENT_ID');
const _center = UserCoordinate(37.5665, 126.9780);

class _MapTestRepository implements ShopRepository {
  _MapTestRepository(this.shops);

  final List<Shop> shops;
  String? lastDetailShopId;

  @override
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async => shops;

  @override
  Future<List<PlaceSearchResult>> searchPlaces({required String query}) async =>
      const [];

  @override
  Future<ShopDetail> detail({
    required String shopId,
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    lastDetailShopId = shopId;
    final shop = shops.firstWhere((shop) => shop.id == shopId);
    return ShopDetail(
      id: shop.id,
      name: shop.name,
      address: shop.address,
      phone: null,
      latitude: shop.latitude,
      longitude: shop.longitude,
      latestDraw: 1234,
      distanceM: shop.distanceM,
      currentRank: shop.resultRank,
      currentSort: sort.apiValue,
      currentRadiusM: radiusM,
      firstCount: shop.firstCount,
      secondCount: shop.secondCount,
      firstPrize: 0,
      secondPrize: 0,
      totalPrize: shop.totalPrize,
      winningDrawCount: 0,
      lastWinningDraw: shop.lastWinningDraw,
      firstRank: 0,
      secondRank: 0,
      totalPrizeRank: 0,
      winningHistory: const [],
    );
  }
}

class _MapTestLocationService implements LocationService {
  @override
  Future<UserCoordinate> current() async =>
      throw const LocationException(LocationFailure.denied);

  @override
  Future<void> openAppSettings() async {}

  @override
  Future<void> openLocationSettings() async {}
}

Shop _shop(String id, double longitude) => Shop(
  id: id,
  name: '테스트 판매점 $id',
  address: '서울특별시 중구',
  latitude: _center.latitude,
  longitude: longitude,
  distanceM: 10,
  resultRank: int.parse(id),
  firstCount: 1,
  secondCount: 2,
  totalPrize: 0,
  lastWinningDraw: 1234,
);

Future<NaverMapController> _pumpMap(
  WidgetTester tester,
  _MapTestRepository repository,
) async {
  final ready = Completer<NaverMapController>();
  final markersSynced = Completer<void>();
  await tester.pumpWidget(
    MaterialApp(
      home: ExploreScreen(
        repository: repository,
        mapEnabled: true,
        locationService: _MapTestLocationService(),
        onMapReady: ready.complete,
        onMarkersSynced: () {
          if (!markersSynced.isCompleted) markersSynced.complete();
        },
      ),
    ),
  );
  await tester.pump(const Duration(seconds: 2));
  final controller = await ready.future.timeout(const Duration(seconds: 10));
  await markersSynced.future.timeout(const Duration(seconds: 10));
  await tester.pump(const Duration(seconds: 2));
  return controller;
}

Future<NPoint> _screenPoint(NaverMapController controller, double longitude) {
  return controller.latLngToScreenLocation(
    NLatLng(_center.latitude, longitude),
  );
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    if (_clientId.isNotEmpty) {
      await FlutterNaverMap().init(clientId: _clientId);
    }
  });

  testWidgets('네이티브 지도에 판매점 핀을 등록한다', (tester) async {
    final shopLongitude = _center.longitude + 0.002;
    final repository = _MapTestRepository([_shop('1', shopLongitude)]);
    final controller = await _pumpMap(tester, repository);
    final point = await _screenPoint(controller, shopLongitude);
    final picked = await controller.pickAll(point, radius: 60);
    final shopMarkers = picked
        .whereType<NOverlayInfo>()
        .where(
          (info) =>
              info.type == NOverlayType.clusterableMarker && info.id == '1',
        )
        .toList();

    expect(shopMarkers, hasLength(1));
  }, skip: _clientId.isEmpty);

  testWidgets('네이티브 지도가 밀집 핀을 클러스터로 묶는다', (tester) async {
    final clusterLongitude = _center.longitude + 0.002;
    final repository = _MapTestRepository([
      for (var index = 0; index < 10; index++)
        _shop('${index + 1}', clusterLongitude + ((index - 5) * 0.000005)),
    ]);
    final controller = await _pumpMap(tester, repository);
    final point = await _screenPoint(controller, clusterLongitude);
    final pickedWhileClustered = await controller.pickAll(point, radius: 100);
    final shopIds = {for (var index = 1; index <= 10; index++) '$index'};
    final visibleLeavesWhileClustered = pickedWhileClustered
        .whereType<NOverlayInfo>()
        .where(
          (info) =>
              info.type == NOverlayType.clusterableMarker &&
              shopIds.contains(info.id),
        )
        .toList();

    expect(visibleLeavesWhileClustered, isEmpty);

    await controller.updateCamera(
      NCameraUpdate.scrollAndZoomTo(
        target: NLatLng(_center.latitude, clusterLongitude),
        zoom: 21,
      ),
    );
    await tester.pump(const Duration(seconds: 2));

    final expandedPoint = await _screenPoint(controller, clusterLongitude);
    final pickedAfterExpansion = await controller.pickAll(
      expandedPoint,
      radius: 100,
    );
    final visibleLeavesAfterExpansion = pickedAfterExpansion
        .whereType<NOverlayInfo>()
        .where((info) => info.type == NOverlayType.clusterableMarker)
        .map((info) => info.id)
        .toSet();

    expect(visibleLeavesAfterExpansion, shopIds);
    expect(repository.lastDetailShopId, isNull);
  }, skip: _clientId.isEmpty);
}
