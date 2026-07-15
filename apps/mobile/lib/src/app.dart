import 'package:flutter/material.dart';

import 'features/explore/data/location_service.dart';
import 'features/explore/data/shop_repository.dart';
import 'features/explore/presentation/explore_screen.dart';

class LottoShopScannerApp extends StatelessWidget {
  const LottoShopScannerApp({
    super.key,
    this.repository,
    this.mapEnabled = false,
    this.locationService,
    this.supportEmail = '',
  });

  final ShopRepository? repository;
  final bool mapEnabled;
  final LocationService? locationService;
  final String supportEmail;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '복권판매점 랭킹',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF176B3A),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F7F4),
        useMaterial3: true,
      ),
      home: ExploreScreen(
        repository: repository ?? ApiShopRepository(),
        mapEnabled: mapEnabled,
        locationService: locationService ?? GeolocatorLocationService(),
        supportEmail: supportEmail,
      ),
    );
  }
}
