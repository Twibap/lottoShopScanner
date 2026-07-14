import 'package:flutter/material.dart';
import 'package:flutter_naver_map/flutter_naver_map.dart';

import 'src/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const clientId = String.fromEnvironment('NAVER_MAP_CLIENT_ID');
  if (clientId.isNotEmpty) {
    await FlutterNaverMap().init(clientId: clientId);
  }
  runApp(LottoShopScannerApp(mapEnabled: clientId.isNotEmpty));
}
