import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lotto_shop_scanner/src/app.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/location_service.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/shop_repository.dart';
import 'package:lotto_shop_scanner/src/features/explore/domain/shop.dart';

class FakeShopRepository implements ShopRepository {
  double? lastLatitude;
  String? lastQuery;

  @override
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    lastLatitude = latitude;
    return const [
      Shop(
        id: 'shop-1',
        name: '행운복권',
        address: '서울특별시 중구 세종대로 1',
        latitude: 37.5665,
        longitude: 126.9780,
        distanceM: 250,
        resultRank: 1,
        firstCount: 3,
        secondCount: 7,
        totalPrize: 1000000,
        lastWinningDraw: 1232,
      ),
    ];
  }

  @override
  Future<List<PlaceSearchResult>> searchPlaces({required String query}) async {
    lastQuery = query;
    return const [
      PlaceSearchResult(
        id: 'place-1',
        title: '부산시청',
        address: '부산 연제구 중앙대로 1001',
        latitude: 35.1796,
        longitude: 129.0756,
        source: 'naver',
      ),
    ];
  }
}

class FakeLocationService implements LocationService {
  @override
  Future<UserCoordinate> current() async =>
      const UserCoordinate(35.1796, 129.0756);

  @override
  Future<void> openAppSettings() async {}

  @override
  Future<void> openLocationSettings() async {}
}

void main() {
  testWidgets('shows nearby shop results and ranking filters', (tester) async {
    final repository = FakeShopRepository();
    await tester.pumpWidget(
      LottoShopScannerApp(
        repository: repository,
        locationService: FakeLocationService(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('내 주변 복권판매점'), findsOneWidget);
    expect(find.text('행운복권'), findsOneWidget);
    expect(find.text('250m'), findsOneWidget);
    expect(find.text('당첨금 순'), findsOneWidget);

    await tester.tap(find.byTooltip('현재 위치'));
    await tester.pumpAndSettle();
    expect(repository.lastLatitude, 35.1796);
  });

  testWidgets('searches places and reloads around selected result', (
    tester,
  ) async {
    final repository = FakeShopRepository();
    await tester.pumpWidget(
      LottoShopScannerApp(
        repository: repository,
        locationService: FakeLocationService(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('지역, 주소, 판매점 검색'), findsOneWidget);
    await tester.tap(find.byType(TextField).first);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(EditableText).last, '부산시청');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(repository.lastQuery, '부산시청');
    await tester.tap(find.widgetWithText(ListTile, '부산시청'));
    await tester.pumpAndSettle();

    expect(repository.lastLatitude, 35.1796);
    expect(find.textContaining('부산시청'), findsOneWidget);
  });
}
