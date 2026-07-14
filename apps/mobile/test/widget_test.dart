import 'package:flutter_test/flutter_test.dart';
import 'package:lotto_shop_scanner/src/app.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/location_service.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/shop_repository.dart';
import 'package:lotto_shop_scanner/src/features/explore/domain/shop.dart';

class FakeShopRepository implements ShopRepository {
  double? lastLatitude;

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
}
