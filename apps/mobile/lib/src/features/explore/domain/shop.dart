class Shop {
  const Shop({
    required this.id,
    required this.name,
    required this.address,
    required this.latitude,
    required this.longitude,
    required this.distanceM,
    required this.resultRank,
    required this.firstCount,
    required this.secondCount,
    required this.totalPrize,
    required this.lastWinningDraw,
  });

  factory Shop.fromJson(Map<String, dynamic> json) {
    int intValue(String key) => (json[key] as num?)?.toInt() ?? 0;
    return Shop(
      id: json['shop_id'] as String,
      name: json['name'] as String,
      address: json['address'] as String,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      distanceM: intValue('distance_m'),
      resultRank: intValue('result_rank'),
      firstCount: intValue('first_count'),
      secondCount: intValue('second_count'),
      totalPrize: intValue('total_prize'),
      lastWinningDraw: intValue('last_winning_draw'),
    );
  }

  final String id;
  final String name;
  final String address;
  final double latitude;
  final double longitude;
  final int distanceM;
  final int resultRank;
  final int firstCount;
  final int secondCount;
  final int totalPrize;
  final int lastWinningDraw;

  String get distanceLabel => distanceM < 1000
      ? '${distanceM}m'
      : '${(distanceM / 1000).toStringAsFixed(1)}km';
}

enum ShopSort {
  distance('가까운 순', 'distance'),
  firstWins('1등 당첨 순', 'first_wins'),
  secondWins('2등 당첨 순', 'second_wins'),
  totalPrize('당첨금 순', 'total_prize'),
  recentWin('최근 당첨 순', 'recent_win');

  const ShopSort(this.label, this.apiValue);

  final String label;
  final String apiValue;
}
