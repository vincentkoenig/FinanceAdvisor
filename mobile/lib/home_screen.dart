import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'main.dart';

class HomeScreen extends StatefulWidget {
  final int userId;

  const HomeScreen({super.key, required this.userId});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _isLoading = true;
  String? _errorMessage;

  double _portfolioValue = 0;
  double _cashBalance = 0;
  double _currentMonthBalance = 0;
  double _totalNetWorth = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // Portfolio-Wert berechnen - gleiche Logik wie im Web-Frontend
      final assetsResponse = await http.get(
        Uri.parse('$apiBaseUrl/users/${widget.userId}/assets'),
      );
      final assets = jsonDecode(assetsResponse.body) as List;

      double portfolioValue = 0;
      for (final asset in assets) {
        portfolioValue += (asset['current_price'] as num) * (asset['quantity'] as num);
      }

      // Budget-Status abrufen
      final budgetResponse = await http.get(
        Uri.parse('$apiBaseUrl/users/${widget.userId}/budget/summary'),
      );
      final budget = jsonDecode(budgetResponse.body);

      setState(() {
        _portfolioValue = portfolioValue;
        _cashBalance = (budget['cumulative_balance'] as num).toDouble();
        _currentMonthBalance = (budget['current_month_balance'] as num).toDouble();
        _totalNetWorth = _portfolioValue + _cashBalance;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Fehler beim Laden: $e';
        _isLoading = false;
      });
    }
  }

  String _formatCurrency(double value) {
    return '${value.toStringAsFixed(2)} €';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('FinTrack')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(child: Text(_errorMessage!))
              : RefreshIndicator(
                  onRefresh: _loadData,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _buildCard('Portfolio-Wert', _formatCurrency(_portfolioValue)),
                      const SizedBox(height: 12),
                      _buildCard(
                        'Cash-Bestand',
                        _formatCurrency(_cashBalance),
                        subtitle: '${_currentMonthBalance >= 0 ? '+' : ''}${_formatCurrency(_currentMonthBalance)} diesen Monat',
                      ),
                      const SizedBox(height: 12),
                      _buildCard('Gesamtvermögen', _formatCurrency(_totalNetWorth)),
                    ],
                  ),
                ),
    );
  }

  Widget _buildCard(String title, String value, {String? subtitle}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(color: Colors.grey, fontSize: 14)),
            const SizedBox(height: 8),
            Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
            if (subtitle != null) ...[
              const SizedBox(height: 4),
              Text(subtitle, style: const TextStyle(color: Colors.grey, fontSize: 13)),
            ],
          ],
        ),
      ),
    );
  }
}