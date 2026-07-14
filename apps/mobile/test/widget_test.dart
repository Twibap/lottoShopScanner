import 'package:flutter_test/flutter_test.dart';
import 'package:lotto_shop_scanner/src/app.dart';
import 'package:lotto_shop_scanner/src/features/explore/data/shop_repository.dart';
import 'package:lotto_shop_scanner/src/features/explore/domain/shop.dart';

class FakeShopRepository implements ShopRepository {
  @override
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    return const [
      Shop(
        id: 'shop-1',
        name: '행운복권',
        address: '서울특별시 중구 세종대로 1',
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

void main() {
  testWidgets('shows nearby shop results and ranking filters', (tester) async {
    await tester.pumpWidget(
      LottoShopScannerApp(repository: FakeShopRepository()),
    );
    await tester.pumpAndSettle();

    expect(find.text('내 주변 복권판매점'), findsOneWidget);
    expect(find.text('행운복권'), findsOneWidget);
    expect(find.text('250m'), findsOneWidget);
    expect(find.text('당첨금 순'), findsOneWidget);
  });
}
