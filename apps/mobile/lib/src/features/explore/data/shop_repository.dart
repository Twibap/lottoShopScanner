import 'dart:convert';
import 'dart:io';

import '../domain/shop.dart';

abstract interface class ShopRepository {
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  });
}

class ApiShopRepository implements ShopRepository {
  ApiShopRepository({
    this.baseUrl = const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
  });

  final String baseUrl;

  @override
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    final uri = Uri.parse('$baseUrl/v1/shops/nearby').replace(
      queryParameters: {
        'lat': '$latitude',
        'lng': '$longitude',
        'radius_m': '$radiusM',
        'sort': sort.apiValue,
        'limit': '100',
      },
    );
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      final request = await client.getUrl(uri);
      final response = await request.close();
      final body = await utf8.decoder.bind(response).join();
      if (response.statusCode != HttpStatus.ok) {
        throw const HttpException('판매점 정보를 불러오지 못했습니다.');
      }
      final payload = jsonDecode(body) as Map<String, dynamic>;
      final items = payload['items'] as List<dynamic>;
      return items
          .cast<Map<String, dynamic>>()
          .map(Shop.fromJson)
          .toList(growable: false);
    } on SocketException {
      throw const HttpException('서버에 연결할 수 없습니다.');
    } finally {
      client.close(force: true);
    }
  }
}
