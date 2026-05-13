import 'package:flutter/material.dart';

import '../theme/cobra_admin_theme.dart';

/// Fournit une phase 0→1 pour animer un dégradé « shimmer » sur les descendants.
class AdminShimmerScope extends StatefulWidget {
  const AdminShimmerScope({super.key, required this.child});

  final Widget child;

  @override
  State<AdminShimmerScope> createState() => _AdminShimmerScopeState();
}

class _AdminShimmerScopeState extends State<AdminShimmerScope> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (_, __) => _ShimmerPhase(
        phase: _controller.value,
        child: widget.child,
      ),
    );
  }
}

class _ShimmerPhase extends InheritedWidget {
  const _ShimmerPhase({required this.phase, required super.child});

  final double phase;

  static double? maybeOf(BuildContext context) {
    final el = context.getElementForInheritedWidgetOfExactType<_ShimmerPhase>();
    final w = el?.widget;
    return w is _ShimmerPhase ? w.phase : null;
  }

  @override
  bool updateShouldNotify(_ShimmerPhase old) => old.phase != phase;
}

/// Barre arrondie type skeleton ; nécessite un [AdminShimmerScope] ancêtre pour le mouvement.
class SkeletonBox extends StatelessWidget {
  const SkeletonBox({
    super.key,
    required this.height,
    this.width,
    this.borderRadius = 12,
  });

  final double height;
  final double? width;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final phase = _ShimmerPhase.maybeOf(context) ?? 0;
    final shift = -1.4 + phase * 2.8;

    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(borderRadius),
        gradient: LinearGradient(
          begin: Alignment(shift, 0),
          end: Alignment(shift + 1.2, 0),
          colors: const [
            Color(0xFFE9D5FF),
            Color(0xFFF5F3FF),
            Color(0xFFE9D5FF),
          ],
          stops: const [0.0, 0.5, 1.0],
        ),
      ),
    );
  }
}

/// Carte vitrée factice (KPI ou ligne de liste).
class GlassSkeletonCard extends StatelessWidget {
  const GlassSkeletonCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: CobraAdminColors.card.withAlpha(230),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withAlpha(180)),
        boxShadow: [
          BoxShadow(
            color: CobraAdminColors.ink.withAlpha(12),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );
  }
}

/// Colonne de tuiles KPI factices.
class KpiSkeletonList extends StatelessWidget {
  const KpiSkeletonList({super.key, this.count = 6});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(
        count,
        (i) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: GlassSkeletonCard(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                SkeletonBox(height: 44, width: 44, borderRadius: 14),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SkeletonBox(height: 22, width: 48, borderRadius: 8),
                      const SizedBox(height: 8),
                      SkeletonBox(height: 12, width: double.infinity, borderRadius: 6),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Carte type alerte / rapport (lignes de texte).
class ListRowSkeletonCard extends StatelessWidget {
  const ListRowSkeletonCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassSkeletonCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SkeletonBox(height: 22, width: 72, borderRadius: 20),
                const Spacer(),
                SkeletonBox(height: 14, width: 36, borderRadius: 6),
              ],
            ),
            const SizedBox(height: 12),
            SkeletonBox(height: 16, width: double.infinity, borderRadius: 8),
            const SizedBox(height: 8),
            SkeletonBox(height: 14, width: 200, borderRadius: 6),
            const SizedBox(height: 10),
            SkeletonBox(height: 40, width: double.infinity, borderRadius: 8),
          ],
        ),
      ),
    );
  }
}

/// Formulaire dispatch (titres + deux champs).
class DispatchFormSkeleton extends StatelessWidget {
  const DispatchFormSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SkeletonBox(height: 28, width: 260, borderRadius: 8),
        const SizedBox(height: 10),
        SkeletonBox(height: 14, width: double.infinity, borderRadius: 6),
        const SizedBox(height: 6),
        SkeletonBox(height: 14, width: 280, borderRadius: 6),
        const SizedBox(height: 20),
        GlassSkeletonCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SkeletonBox(height: 16, width: 200, borderRadius: 6),
              const SizedBox(height: 10),
              SkeletonBox(height: 48, width: double.infinity, borderRadius: 12),
            ],
          ),
        ),
        const SizedBox(height: 14),
        GlassSkeletonCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SkeletonBox(height: 16, width: 160, borderRadius: 6),
              const SizedBox(height: 10),
              SkeletonBox(height: 48, width: double.infinity, borderRadius: 12),
            ],
          ),
        ),
        const SizedBox(height: 22),
        SkeletonBox(height: 52, width: double.infinity, borderRadius: 14),
      ],
    );
  }
}
