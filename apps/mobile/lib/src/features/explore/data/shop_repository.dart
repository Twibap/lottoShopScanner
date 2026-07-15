import 'dart:convert';
import 'dart:io';

import '../domain/shop.dart';

class PlaceSearchResult {
  const PlaceSearchResult({
    required this.id,
    required this.title,
    required this.address,
    required this.latitude,
    required this.longitude,
    required this.source,
  });

  final String id;
  final String title;
  final String address;
  final double latitude;
  final double longitude;
  final String source;

  factory PlaceSearchResult.fromJson(Map<String, dynamic> json) {
    return PlaceSearchResult(
      id: json['place_id'] as String,
      title: json['title'] as String,
      address: json['address'] as String,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      source: json['source'] as String? ?? 'shop',
    );
  }
}

abstract interface class ShopRepository {
  Future<List<Shop>> nearby({
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  });

  Future<List<PlaceSearchResult>> searchPlaces({required String query});

  Future<ShopDetail> detail({
    required String shopId,
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

  @override
  Future<List<PlaceSearchResult>> searchPlaces({required String query}) async {
    final uri = Uri.parse(
      '$baseUrl/v1/places/search',
    ).replace(queryParameters: {'q': query, 'limit': '10'});
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      final request = await client.getUrl(uri);
      final response = await request.close();
      final body = await utf8.decoder.bind(response).join();
      if (response.statusCode != HttpStatus.ok) {
        throw const HttpException('검색 결과를 불러오지 못했습니다.');
      }
      final payload = jsonDecode(body) as Map<String, dynamic>;
      final items = payload['items'] as List<dynamic>;
      return items
          .cast<Map<String, dynamic>>()
          .map(PlaceSearchResult.fromJson)
          .toList(growable: false);
    } on SocketException {
      throw const HttpException('서버에 연결할 수 없습니다.');
    } finally {
      client.close(force: true);
    }
  }

  @override
  Future<ShopDetail> detail({
    required String shopId,
    required double latitude,
    required double longitude,
    required int radiusM,
    required ShopSort sort,
  }) async {
    final uri = Uri.parse('$baseUrl/v1/shops/$shopId').replace(
      queryParameters: {
        'lat': '$latitude',
        'lng': '$longitude',
        'radius_m': '$radiusM',
        'sort': sort.apiValue,
      },
    );
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      final request = await client.getUrl(uri);
      final response = await request.close();
      final body = await utf8.decoder.bind(response).join();
      if (response.statusCode == HttpStatus.notFound) {
        throw const HttpException('판매점을 찾을 수 없습니다.');
      }
      if (response.statusCode != HttpStatus.ok) {
        throw const HttpException('판매점 상세 정보를 불러오지 못했습니다.');
      }
      return ShopDetail.fromJson(jsonDecode(body) as Map<String, dynamic>);
    } on SocketException {
      throw const HttpException('서버에 연결할 수 없습니다.');
    } finally {
      client.close(force: true);
    }
  }
}
