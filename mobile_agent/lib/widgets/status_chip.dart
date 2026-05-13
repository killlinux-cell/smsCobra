import 'package:flutter/material.dart';

class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.ok, required this.label});

  final bool ok;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(
      backgroundColor: ok
          ? Colors.green.withAlpha((0.15 * 255).round())
          : Colors.grey.withAlpha((0.10 * 255).round()),
      label: Text(
        label,
        style: TextStyle(
          color: ok ? Colors.green.shade700 : Colors.black54,
          fontWeight: FontWeight.w600,
        ),
      ),
      avatar: Icon(
        ok ? Icons.check_circle : Icons.radio_button_unchecked,
        size: 16,
        color: ok ? Colors.green.shade700 : Colors.black38,
      ),
    );
  }
}

