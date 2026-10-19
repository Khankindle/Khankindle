import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

const _categories = [
  'Tuckshop / grocery',
  'Fresh produce / market stall',
  'Clothing and textiles',
  'Fast food / kitchen',
  'Hair and beauty',
  'Airtime, phones, and electronics',
  'Hardware and building supplies',
  'Agriculture and livestock',
  'Transport and logistics',
  'Repairs and other services',
  'Cross-border trading',
  'Other',
];

void main() {
  runApp(const PocketLedgerApp());
}

class PocketLedgerApp extends StatelessWidget {
  const PocketLedgerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PocketLedger',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFE8782F),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF8F8F7),
        useMaterial3: true,
      ),
      home: const CapturePage(),
    );
  }
}

class CapturePage extends StatefulWidget {
  const CapturePage({super.key});

  @override
  State<CapturePage> createState() => _CapturePageState();
}

class _CapturePageState extends State<CapturePage> {
  final _name = TextEditingController(text: 'Gogo Chipo fresh produce');
  final _server = TextEditingController(text: 'http://10.0.2.2:8765');
  String _category = _categories[1];
  String _language = 'English';
  XFile? _photo;
  Map<String, dynamic>? _result;
  Map<String, dynamic>? _health;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _server.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source) async {
    final photo = await ImagePicker().pickImage(
      source: source,
      maxWidth: 1024,
      imageQuality: 70,
    );
    if (photo == null) return;
    setState(() {
      _photo = photo;
      _result = null;
      _error = null;
    });
  }

  String get _baseUrl => _server.text.trim().replaceAll(RegExp(r'/+$'), '');

  /// Fetches the Business Health Score for this trader without a new capture.
  Future<void> _checkScore() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final uri = Uri.parse('$_baseUrl/api/health').replace(
        queryParameters: {'business_name': _name.text.trim(), 'category': _category},
      );
      final response = await http.get(uri);
      final body = jsonDecode(response.body);
      if (response.statusCode != 200 || body is! Map<String, dynamic>) {
        throw Exception('Could not load the health score.');
      }
      final health = body['health'];
      setState(() => _health = health is Map<String, dynamic> ? health : null);
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _extract() async {
    final photo = _photo;
    if (photo == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final bytes = await photo.readAsBytes();
      final uri = Uri.parse('$_baseUrl/api/extract');
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'source': 'image',
          'mime_type': 'image/jpeg',
          'data': base64Encode(bytes),
          'business_name': _name.text.trim(),
          'category': _category,
        }),
      );
      final body = jsonDecode(response.body);
      if (body is! Map<String, dynamic>) {
        throw Exception('The server did not return a statement.');
      }
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'Could not read the ledger.');
      }
      final health = body['health'];
      setState(() {
        _result = body;
        _health = health is Map<String, dynamic> ? health : null;
      });
    } catch (error) {
      setState(() => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _summary(Map<String, dynamic> result) {
    switch (_language) {
      case 'ChiShona':
        return '${result['summary_shona'] ?? 'Hapana pfupiso.'}';
      case 'IsiNdebele':
        return '${result['summary_ndebele'] ?? 'Asikho isifinyezo.'}';
      default:
        return '${result['business_health_summary'] ?? 'Summary unavailable.'}';
    }
  }

  String _money(dynamic value) {
    final number = value is num ? value.toDouble() : double.tryParse('$value') ?? 0;
    return '\$${number.toStringAsFixed(2)}';
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: const Text('PocketLedger')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            'Photograph a notebook page. Gemini reads it on your computer, so the API key never goes on the phone.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            decoration: const InputDecoration(
              labelText: 'Business name',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(
              labelText: 'Category',
              border: OutlineInputBorder(),
            ),
            items: [
              for (final category in _categories)
                DropdownMenuItem(value: category, child: Text(category)),
            ],
            onChanged: (value) {
              if (value != null) setState(() => _category = value);
            },
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _server,
            decoration: const InputDecoration(
              labelText: 'Laptop API address',
              helperText: 'Emulator: 10.0.2.2. A real phone uses the laptop Wi-Fi address.',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _busy ? null : _checkScore,
              icon: const Icon(Icons.insights_outlined),
              label: const Text('Check health score'),
            ),
          ),
          if (_health != null && result == null) ...[
            HealthCard(health: _health!, language: _language),
          ],
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _busy ? null : () => _pick(ImageSource.camera),
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Camera'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _busy ? null : () => _pick(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library_outlined),
                  label: const Text('Gallery'),
                ),
              ),
            ],
          ),
          if (_photo != null) ...[
            const SizedBox(height: 12),
            Text(_photo!.name, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _busy ? null : _extract,
              child: Text(_busy ? 'Reading the ledger…' : 'Process ledger'),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          if (result != null) ...[
            const SizedBox(height: 24),
            Text(
              '${result['business_name'] ?? _name.text} · ${result['date'] ?? 'Unspecified'}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'English', label: Text('English')),
                ButtonSegment(value: 'ChiShona', label: Text('ChiShona')),
                ButtonSegment(value: 'IsiNdebele', label: Text('IsiNdebele')),
              ],
              selected: {_language},
              onSelectionChanged: (value) => setState(() => _language = value.first),
            ),
            const SizedBox(height: 12),
            _Metric(label: 'Recorded revenue', value: _money(result['total_revenue_usd'])),
            _Metric(label: 'Cash received', value: _money(result['total_cash_usd'])),
            _Metric(label: 'Outstanding credit', value: _money(result['total_credit_outstanding_usd'])),
            const SizedBox(height: 12),
            if (_health != null) ...[
              HealthCard(health: _health!, language: _language),
              const SizedBox(height: 12),
            ],
            Text(_summary(result)),
            const SizedBox(height: 16),
            Text('Transactions', style: Theme.of(context).textTheme.titleMedium),
            for (final row in (result['transactions'] as List? ?? []))
              if (row is Map)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${row['item'] ?? 'Item'}'),
                  subtitle: Text('${row['payment_type'] ?? ''} ${row['debtor'] ?? ''}'.trim()),
                  trailing: Text(_money(row['amount_usd'])),
                ),
            const SizedBox(height: 8),
            Text(
              'AI-assisted indexing. This is not an audit and it is not a loan decision.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label),
          Text(value, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}

/// Business Health Score card (SPEC.md §7). `health` is the `health` object from the API.
class HealthCard extends StatelessWidget {
  const HealthCard({super.key, required this.health, required this.language});

  final Map<String, dynamic> health;
  final String language;

  String _money(dynamic value) {
    final number = value is num ? value.toDouble() : double.tryParse('$value') ?? 0;
    return '\$${number.toStringAsFixed(2)}';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final score = health['score'];
    final status = '${health['status'] ?? 'Not enough data'}';
    final window = health['window'];
    final days = window is Map ? window['trading_days'] ?? 0 : 0;

    final children = <Widget>[
      Text('Business health score', style: theme.textTheme.titleMedium),
      const SizedBox(height: 8),
    ];

    if (score == null) {
      children.add(Text('Record ${health['record_more_days'] ?? 5} more trading day(s) to get your score.'));
      children.add(Text('$days trading day(s) recorded so far.', style: theme.textTheme.bodySmall));
    } else {
      final bands = health['band_local'];
      final band = bands is Map ? '${bands[language] ?? health['band']}' : '${health['band']}';
      children.add(Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text('$score/100',
              style: theme.textTheme.headlineMedium?.copyWith(color: theme.colorScheme.primary)),
          const SizedBox(width: 12),
          Flexible(child: Text(band, style: theme.textTheme.titleMedium)),
        ],
      ));
      children.add(Text('$status · ${health['evidence_level'] ?? 'Self-reported'} · $days trading days',
          style: theme.textTheme.bodySmall));

      final actions = health['actions'];
      if (actions is List && actions.isNotEmpty) {
        children.add(const SizedBox(height: 8));
        children.add(Text('What is lowering your score', style: theme.textTheme.labelLarge));
        for (final action in actions) {
          if (action is Map) children.add(Text('• ${action['English'] ?? ''}'));
        }
      }

      final affordability = health['affordability'];
      if (affordability is Map) {
        children.add(const SizedBox(height: 8));
        children.add(Text(
          'Safe daily repayment up to ${_money(affordability['safe_daily_repayment_usd'])}. '
          '30-day total up to ${_money(affordability['indicative_amount_30d_usd'])}.',
        ));
        children.add(Text('${affordability['note'] ?? ''}', style: theme.textTheme.bodySmall));
      }
    }

    children.add(const SizedBox(height: 8));
    children.add(Text('Health score, not a credit score or a loan decision.', style: theme.textTheme.bodySmall));

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: children),
      ),
    );
  }
}
