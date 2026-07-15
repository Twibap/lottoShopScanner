import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lotto_shop_scanner/src/app.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/location_service.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/shop_repository.dart';
import 'package:lotto_shop_scanner/src/features/explore/domain/shop.dart';

class FakeShopRepository implements ShopRepository {
  double? lastLatitude;
  String? lastQuery;
  String? lastDetailShopId;

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

  @override
  Future<ShopDetail> detail({
    required String shopId,
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    lastDetailShopId = shopId;
    return const ShopDetail(
      id: 'shop-1',
      name: '행운복권',
      address: '서울특별시 중구 세종대로 1',
      phone: '02-123-4567',
      latitude: 37.5665,
      longitude: 126.9780,
      latestDraw: 1232,
      distanceM: 250,
      currentRank: 1,
      currentSort: 'distance',
      currentRadiusM: 3000,
      firstCount: 3,
      secondCount: 7,
      firstPrize: 3000000000,
      secondPrize: 1000000,
      totalPrize: 3001000000,
      winningDrawCount: 8,
      lastWinningDraw: 1232,
      firstRank: 10,
      secondRank: 20,
      totalPrizeRank: 30,
      winningHistory: [
        WinningHistory(
          draw: 1232,
          prizeRank: 1,
          prizeAmount: 3000000000,
          drawDate: '2026-07-11',
          winMethod: '자동',
        ),
      ],
    );
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

  testWidgets('opens shop detail from a result card', (tester) async {
    final repository = FakeShopRepository();
    await tester.pumpWidget(
      LottoShopScannerApp(
        repository: repository,
        locationService: FakeLocationService(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('행운복권'));
    await tester.pumpAndSettle();

    expect(repository.lastDetailShopId, 'shop-1');
    expect(find.text('당첨 통계'), findsOneWidget);
    expect(find.text('길찾기'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('정보 오류 제보'),
      240,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('정보 오류 제보'), findsOneWidget);
    await tester.tap(find.text('정보 오류 제보'));
    await tester.pumpAndSettle();
    expect(find.text('지원 이메일은 출시 전에 연결됩니다.'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('전국 보조 순위'),
      240,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('전국 보조 순위'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('1232회 · 2026-07-11'),
      240,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('1232회 · 2026-07-11'), findsOneWidget);
  });
}
