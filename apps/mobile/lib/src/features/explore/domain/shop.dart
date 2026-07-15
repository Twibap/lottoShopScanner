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

class WinningHistory {
  const WinningHistory({
    required this.draw,
    required this.prizeRank,
    required this.prizeAmount,
    required this.drawDate,
    this.winMethod,
  });

  factory WinningHistory.fromJson(Map<String, dynamic> json) {
    return WinningHistory(
      draw: (json['draw'] as num).toInt(),
      prizeRank: (json['prize_rank'] as num).toInt(),
      prizeAmount: (json['prize_amount'] as num).toInt(),
      drawDate: json['draw_date'] as String,
      winMethod: json['win_method'] as String?,
    );
  }

  final int draw;
  final int prizeRank;
  final int prizeAmount;
  final String drawDate;
  final String? winMethod;
}

class ShopDetail {
  const ShopDetail({
    required this.id,
    required this.name,
    required this.address,
    required this.latitude,
    required this.longitude,
    required this.latestDraw,
    required this.firstCount,
    required this.secondCount,
    required this.firstPrize,
    required this.secondPrize,
    required this.totalPrize,
    required this.winningDrawCount,
    required this.lastWinningDraw,
    required this.firstRank,
    required this.secondRank,
    required this.totalPrizeRank,
    required this.winningHistory,
    this.phone,
    this.distanceM,
    this.currentRank,
    this.currentSort,
    this.currentRadiusM,
  });

  factory ShopDetail.fromJson(Map<String, dynamic> json) {
    int intValue(String key) => (json[key] as num?)?.toInt() ?? 0;
    return ShopDetail(
      id: json['shop_id'] as String,
      name: json['name'] as String,
      address: json['address'] as String,
      phone: json['phone'] as String?,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      latestDraw: intValue('latest_draw'),
      distanceM: (json['distance_m'] as num?)?.toInt(),
      currentRank: (json['current_rank'] as num?)?.toInt(),
      currentSort: json['current_sort'] as String?,
      currentRadiusM: (json['current_radius_m'] as num?)?.toInt(),
      firstCount: intValue('first_count'),
      secondCount: intValue('second_count'),
      firstPrize: intValue('first_prize'),
      secondPrize: intValue('second_prize'),
      totalPrize: intValue('total_prize'),
      winningDrawCount: intValue('winning_draw_count'),
      lastWinningDraw: intValue('last_winning_draw'),
      firstRank: intValue('first_rank'),
      secondRank: intValue('second_rank'),
      totalPrizeRank: intValue('total_prize_rank'),
      winningHistory: (json['winning_history'] as List<dynamic>)
          .cast<Map<String, dynamic>>()
          .map(WinningHistory.fromJson)
          .toList(growable: false),
    );
  }

  final String id;
  final String name;
  final String address;
  final String? phone;
  final double latitude;
  final double longitude;
  final int latestDraw;
  final int? distanceM;
  final int? currentRank;
  final String? currentSort;
  final int? currentRadiusM;
  final int firstCount;
  final int secondCount;
  final int firstPrize;
  final int secondPrize;
  final int totalPrize;
  final int winningDrawCount;
  final int lastWinningDraw;
  final int firstRank;
  final int secondRank;
  final int totalPrizeRank;
  final List<WinningHistory> winningHistory;

  String get distanceLabel {
    final distance = distanceM;
    if (distance == null) return '거리 정보 없음';
    return distance < 1000
        ? '${distance}m'
        : '${(distance / 1000).toStringAsFixed(1)}km';
  }
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
