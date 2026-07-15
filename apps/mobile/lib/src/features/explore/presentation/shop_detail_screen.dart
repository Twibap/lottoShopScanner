import 'dart:io';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/shop_repository.dart';
import '../domain/shop.dart';

class ShopDetailScreen extends StatefulWidget {
  const ShopDetailScreen({
    super.key,
    required this.repository,
    required this.shop,
    required this.latitude,
    required this.longitude,
    required this.radiusM,
    required this.sort,
    this.supportEmail = '',
  });

  final ShopRepository repository;
  final Shop shop;
  final double latitude;
  final double longitude;
  final int radiusM;
  final ShopSort sort;
  final String supportEmail;

  @override
  State<ShopDetailScreen> createState() => _ShopDetailScreenState();
}

class _ShopDetailScreenState extends State<ShopDetailScreen> {
  late Future<ShopDetail> _detail;

  @override
  void initState() {
    super.initState();
    _detail = _load();
  }

  Future<ShopDetail> _load() {
    return widget.repository.detail(
      shopId: widget.shop.id,
      latitude: widget.latitude,
      longitude: widget.longitude,
      radiusM: widget.radiusM,
      sort: widget.sort,
    );
  }

  void _retry() {
    setState(() => _detail = _load());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.shop.name)),
      body: FutureBuilder<ShopDetail>(
        future: _detail,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _DetailMessage(
              title: snapshot.error.toString().replaceFirst(
                'HttpException: ',
                '',
              ),
              onRetry: _retry,
            );
          }
          return _DetailBody(
            detail: snapshot.requireData,
            supportEmail: widget.supportEmail,
          );
        },
      ),
    );
  }
}

class _DetailBody extends StatelessWidget {
  const _DetailBody({required this.detail, required this.supportEmail});

  final ShopDetail detail;
  final String supportEmail;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
      children: [
        Text(detail.name, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        Text(detail.address),
        if (detail.phone != null && detail.phone!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(detail.phone!),
        ],
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _InfoChip(icon: Icons.place_outlined, label: detail.distanceLabel),
            _InfoChip(icon: Icons.update, label: '기준 ${detail.latestDraw}회'),
            if (detail.currentRank != null)
              _InfoChip(
                icon: Icons.format_list_numbered,
                label: '현재 반경 내 ${detail.currentRank}위',
              ),
          ],
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: () => _openDirections(context, detail),
          icon: const Icon(Icons.directions),
          label: const Text('길찾기'),
        ),
        const SizedBox(height: 20),
        _SectionTitle('당첨 통계'),
        _StatsGrid(detail: detail),
        const SizedBox(height: 20),
        _SectionTitle('전국 보조 순위'),
        _RankRows(detail: detail),
        const SizedBox(height: 20),
        _SectionTitle('당첨 이력'),
        if (detail.winningHistory.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text('당첨 이력이 없습니다.'),
          )
        else
          for (final history in detail.winningHistory)
            _HistoryTile(history: history),
        const SizedBox(height: 20),
        const Text(
          '과거 당첨 이력은 향후 당첨 확률을 보장하지 않습니다. 판매점·당첨 결과는 동행복권 공개 데이터 기반입니다.',
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => _reportIncorrectInfo(context, detail, supportEmail),
          icon: const Icon(Icons.outgoing_mail),
          label: const Text('정보 오류 제보'),
        ),
      ],
    );
  }
}

Future<void> _openDirections(BuildContext context, ShopDetail detail) async {
  final primary = Platform.isIOS
      ? Uri.https('maps.apple.com', '/', {
          'daddr': '${detail.latitude},${detail.longitude}',
          'q': detail.name,
        })
      : Uri.parse(
          'geo:${detail.latitude},${detail.longitude}?q=${Uri.encodeComponent('${detail.latitude},${detail.longitude}(${detail.name})')}',
        );
  final fallback = Uri.parse(
    'https://map.naver.com/p/search/${Uri.encodeComponent(detail.address)}',
  );

  if (await launchUrl(primary, mode: LaunchMode.externalApplication)) return;
  if (await launchUrl(fallback, mode: LaunchMode.externalApplication)) return;
  if (context.mounted) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('길찾기를 열 수 없습니다.')));
  }
}

Future<void> _reportIncorrectInfo(
  BuildContext context,
  ShopDetail detail,
  String supportEmail,
) async {
  final email = supportEmail.trim();
  if (email.isEmpty) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('지원 이메일은 출시 전에 연결됩니다.')));
    return;
  }

  final uri = Uri(
    scheme: 'mailto',
    path: email,
    queryParameters: {
      'subject': '[Lotto Shop Scanner] 판매점 정보 오류 제보',
      'body': [
        '아래 판매점 정보에 오류가 있어 제보합니다.',
        '',
        '판매점 ID: ${detail.id}',
        '상호명: ${detail.name}',
        '주소: ${detail.address}',
        '데이터 기준 회차: ${detail.latestDraw}회',
        '',
        '제보 유형: 위치/주소, 폐점/상호, 당첨 이력, 기타 중 하나를 적어 주세요.',
        '상세 내용:',
      ].join('\n'),
    },
  );

  if (await launchUrl(uri, mode: LaunchMode.externalApplication)) return;
  if (context.mounted) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('이메일 앱을 열 수 없습니다.')));
  }
}

class _StatsGrid extends StatelessWidget {
  const _StatsGrid({required this.detail});

  final ShopDetail detail;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 2.35,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      children: [
        _StatTile(label: '1등', value: '${detail.firstCount}회'),
        _StatTile(label: '2등', value: '${detail.secondCount}회'),
        _StatTile(label: '당첨 회차', value: '${detail.winningDrawCount}회'),
        _StatTile(label: '최근 당첨', value: '${detail.lastWinningDraw}회'),
        _StatTile(label: '1등 당첨금', value: _won(detail.firstPrize)),
        _StatTile(label: '누적 당첨금', value: _won(detail.totalPrize)),
      ],
    );
  }
}

class _RankRows extends StatelessWidget {
  const _RankRows({required this.detail});

  final ShopDetail detail;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _RankRow(label: '전국 1등 횟수 순위', value: '${detail.firstRank}위'),
        _RankRow(label: '전국 2등 횟수 순위', value: '${detail.secondRank}위'),
        _RankRow(label: '전국 당첨금 순위', value: '${detail.totalPrizeRank}위'),
      ],
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.history});

  final WinningHistory history;

  @override
  Widget build(BuildContext context) {
    final method = history.winMethod?.trim();
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(child: Text('${history.prizeRank}등')),
        title: Text('${history.draw}회 · ${history.drawDate}'),
        subtitle: Text(
          method == null || method.isEmpty ? '구매 방식 정보 없음' : method,
        ),
        trailing: Text(_won(history.prizeAmount)),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(avatar: Icon(icon, size: 18), label: Text(label));
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label, style: Theme.of(context).textTheme.labelMedium),
            const SizedBox(height: 2),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _RankRow extends StatelessWidget {
  const _RankRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: Theme.of(context).textTheme.titleLarge),
    );
  }
}

class _DetailMessage extends StatelessWidget {
  const _DetailMessage({required this.title, required this.onRetry});

  final String title;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 48),
          const SizedBox(height: 12),
          Text(title),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onRetry, child: const Text('다시 시도')),
        ],
      ),
    );
  }
}

String _won(int value) {
  final raw = value.toString();
  final buffer = StringBuffer();
  for (var index = 0; index < raw.length; index += 1) {
    if (index > 0 && (raw.length - index) % 3 == 0) buffer.write(',');
    buffer.write(raw[index]);
  }
  return '$buffer원';
}
