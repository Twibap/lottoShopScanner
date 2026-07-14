import 'package:flutter/material.dart';

import '../data/shop_repository.dart';
import '../domain/shop.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key, required this.repository});

  final ShopRepository repository;

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  static const _latitude = 37.5665;
  static const _longitude = 126.9780;
  static const _radii = [1000, 3000, 5000, 10000];

  var _radiusM = 3000;
  var _sort = ShopSort.distance;
  var _loading = true;
  String? _error;
  List<Shop> _shops = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final shops = await widget.repository.nearby(
        latitude: _latitude,
        longitude: _longitude,
        radiusM: _radiusM,
        sort: _sort,
      );
      if (mounted) {
        setState(() => _shops = shops);
      }
    } on Exception catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('HttpException: ', ''),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('내 주변 복권판매점'),
        actions: [
          IconButton(
            tooltip: '랭킹 기준 안내',
            onPressed: () => showDialog<void>(
              context: context,
              builder: (context) => const _RankingNotice(),
            ),
            icon: const Icon(Icons.info_outline),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            const _SearchBar(),
            _MapPlaceholder(onRefresh: _load),
            _Filters(
              radiusM: _radiusM,
              sort: _sort,
              radii: _radii,
              onRadiusChanged: (value) {
                setState(() => _radiusM = value);
                _load();
              },
              onSortChanged: (value) {
                setState(() => _sort = value);
                _load();
              },
            ),
            Expanded(child: _buildResults()),
          ],
        ),
      ),
    );
  }

  Widget _buildResults() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return _MessageState(
        icon: Icons.cloud_off_outlined,
        title: _error!,
        actionLabel: '다시 시도',
        onAction: _load,
      );
    }
    if (_shops.isEmpty) {
      return _MessageState(
        icon: Icons.location_off_outlined,
        title: '이 반경에는 판매점이 없습니다.',
        actionLabel: '반경 넓히기',
        onAction: () {
          setState(() => _radiusM = 10000);
          _load();
        },
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        itemCount: _shops.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                '현재 반경 내 ${_shops.length}곳 · ${_sort.label}',
                style: Theme.of(context).textTheme.labelLarge,
              ),
            );
          }
          return _ShopCard(shop: _shops[index - 1]);
        },
      ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: TextField(
        readOnly: true,
        decoration: InputDecoration(
          hintText: '지역이나 주소 검색',
          prefixIcon: const Icon(Icons.search),
          suffixIcon: IconButton(
            tooltip: '현재 위치',
            onPressed: () {},
            icon: const Icon(Icons.my_location),
          ),
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
        ),
      ),
    );
  }
}

class _MapPlaceholder extends StatelessWidget {
  const _MapPlaceholder({required this.onRefresh});

  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 180,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: const Color(0xFFDDE9DF),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          const Icon(Icons.map_outlined, size: 72, color: Color(0xFF6B8C73)),
          Positioned(
            bottom: 12,
            child: FilledButton.tonalIcon(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              label: const Text('이 지역 다시 검색'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Filters extends StatelessWidget {
  const _Filters({
    required this.radiusM,
    required this.sort,
    required this.radii,
    required this.onRadiusChanged,
    required this.onSortChanged,
  });

  final int radiusM;
  final ShopSort sort;
  final List<int> radii;
  final ValueChanged<int> onRadiusChanged;
  final ValueChanged<ShopSort> onSortChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        scrollDirection: Axis.horizontal,
        children: [
          DropdownMenu<int>(
            width: 112,
            initialSelection: radiusM,
            onSelected: (value) {
              if (value != null) onRadiusChanged(value);
            },
            dropdownMenuEntries: [
              for (final radius in radii)
                DropdownMenuEntry(value: radius, label: '${radius ~/ 1000}km'),
            ],
          ),
          const SizedBox(width: 8),
          for (final option in ShopSort.values) ...[
            ChoiceChip(
              label: Text(option.label),
              selected: option == sort,
              onSelected: (_) => onSortChanged(option),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class _ShopCard extends StatelessWidget {
  const _ShopCard({required this.shop});

  final Shop shop;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.all(14),
        leading: CircleAvatar(child: Text('${shop.resultRank}')),
        title: Text(shop.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(shop.address, maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 5),
              Text(
                '1등 ${shop.firstCount}회 · 2등 ${shop.secondCount}회 · 최근 ${shop.lastWinningDraw}회',
              ),
            ],
          ),
        ),
        trailing: Text(shop.distanceLabel),
        onTap: () {},
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.actionLabel,
    required this.onAction,
  });

  final IconData icon;
  final String title;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 48),
          const SizedBox(height: 12),
          Text(title),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onAction, child: Text(actionLabel)),
        ],
      ),
    );
  }
}

class _RankingNotice extends StatelessWidget {
  const _RankingNotice();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('랭킹 기준'),
      content: const Text(
        '현재 검색 반경 안의 판매점만 비교합니다. 과거 당첨 이력은 향후 당첨 확률을 보장하지 않습니다.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('확인'),
        ),
      ],
    );
  }
}
