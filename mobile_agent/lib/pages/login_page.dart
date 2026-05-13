import 'package:flutter/material.dart';

import '../services/cobra_api.dart';
import 'agent_home_page.dart';
import 'face_capture_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.api});
  final CobraApi api;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool loading = false;
  String? error;
  String? identifiedGuard;
  bool controllerMode = false;
  bool loadingSites = false;
  List<EntrySite> entrySites = const [];
  EntrySite? selectedSite;

  @override
  void initState() {
    super.initState();
    _loadSites();
  }

  Future<void> _loadSites() async {
    setState(() => loadingSites = true);
    try {
      final sites = await widget.api.fetchEntrySites();
      if (!mounted) return;
      setState(() {
        entrySites = sites;
        if (sites.isNotEmpty) selectedSite = sites.first;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => error = "Impossible de charger la liste des sites.");
    } finally {
      if (mounted) setState(() => loadingSites = false);
    }
  }

  String _mapError(Object e) {
    final s = e.toString();
    if (s.contains("network_unreachable")) {
      return "Impossible de joindre le serveur. Verifiez le Wi-Fi, l'adresse du serveur ci-dessous, et le pare-feu (port 8000).";
    }
    if (s.contains("network_timeout")) {
      return "Le serveur met trop longtemps a repondre. Reessayez.";
    }
    if (s.contains("Visage non reconnu")) {
      return "Visage non reconnu ou aucun service planifie aujourd'hui.";
    }
    if (s.contains("Aucun vigile planifié")) {
      return "Aucun vigile planifie avec photo d'enrolement disponible.";
    }
    if (s.contains("Aucun visage détecté")) {
      return "Aucun visage detecte. Reprenez la photo en vous cadrant mieux.";
    }
    if (s.contains("Aucun contrôleur actif")) {
      return "Aucun contrôleur avec photo n'est autorisé sur ce site.";
    }
    if (s.contains("Visage non reconnu pour un contrôleur")) {
      return "Visage non reconnu pour un contrôleur autorisé sur ce site.";
    }
    if (s.contains("site_id invalide")) {
      return "Sélectionnez un site valide.";
    }
    if (s.contains("face_identify_http")) {
      return "Erreur serveur lors de l'identification. Reessayez ou contactez le support.";
    }
    return "Connexion impossible. Verifiez la photo et le serveur.";
  }

  Future<void> _faceLogin() async {
    setState(() {
      loading = true;
      error = null;
      identifiedGuard = null;
    });
    final imgPath = await FaceCapturePage.capture(
      context,
      title: "Identification par visage",
      hint: "Placez votre visage dans le cadran ovale puis prenez la photo.",
    );
    if (imgPath == null) {
      if (mounted) setState(() => loading = false);
      return;
    }
    try {
      final guardUsername = await widget.api.faceIdentifyLogin(imgPath);
      identifiedGuard = guardUsername;
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => AgentHomePage(api: widget.api)),
      );
    } catch (e) {
      if (mounted) setState(() => error = _mapError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _controllerCheckin() async {
    if (selectedSite == null) {
      setState(() => error = "Sélectionnez d'abord un site.");
      return;
    }
    setState(() {
      loading = true;
      error = null;
      identifiedGuard = null;
    });
    final imgPath = await FaceCapturePage.capture(
      context,
      title: "Passage contrôleur",
      hint: "Placez le visage du contrôleur dans le cadran puis prenez la photo.",
    );
    if (imgPath == null) {
      if (mounted) setState(() => loading = false);
      return;
    }
    try {
      final msg = await widget.api.controllerFaceCheckin(
        siteId: selectedSite!.id,
        selfiePath: imgPath,
      );
      if (mounted) {
        setState(() => identifiedGuard = msg);
      }
    } catch (e) {
      if (mounted) setState(() => error = _mapError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              cs.primaryContainer.withAlpha(230),
              cs.primary.withAlpha(200),
            ],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Image.asset(
                      'assets/images/sms_logo.png',
                      height: 72,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      controllerMode
                          ? "Passage contrôleur par visage"
                          : "Acces vigile par visage",
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 18,
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      controllerMode
                          ? "Sélectionnez un site puis prenez un selfie du contrôleur. Le passage est tracé sur le dashboard."
                          : "Aucun mot de passe. Prenez un selfie: l'app identifie le vigile et verifie qu'il est planifie.",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: cs.onSurfaceVariant,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      "Serveur : ${CobraApi.apiBase}",
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade700,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    if (identifiedGuard != null &&
                        identifiedGuard!.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(
                        identifiedGuard!,
                        style: const TextStyle(
                          color: Colors.green,
                          fontSize: 13,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    if (error != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        error!,
                        style: const TextStyle(color: Colors.red, fontSize: 13),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: 16),
                    SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment<bool>(
                          value: false,
                          icon: Icon(Icons.security_rounded),
                          label: Text("Vigile"),
                        ),
                        ButtonSegment<bool>(
                          value: true,
                          icon: Icon(Icons.badge_rounded),
                          label: Text("Contrôleur"),
                        ),
                      ],
                      selected: {controllerMode},
                      onSelectionChanged: loading
                          ? null
                          : (s) {
                              setState(() {
                                controllerMode = s.first;
                                identifiedGuard = null;
                                error = null;
                              });
                            },
                    ),
                    if (controllerMode) ...[
                      const SizedBox(height: 12),
                      if (loadingSites)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8),
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      else if (entrySites.isEmpty)
                        const Text(
                          "Aucun site disponible.",
                          style: TextStyle(color: Colors.red, fontSize: 12),
                        )
                      else
                        DropdownButtonFormField<int>(
                          initialValue: selectedSite?.id,
                          decoration: const InputDecoration(
                            labelText: "Site de passage",
                            border: OutlineInputBorder(),
                          ),
                          items: entrySites
                              .map(
                                (s) => DropdownMenuItem<int>(
                                  value: s.id,
                                  child: Text(s.name),
                                ),
                              )
                              .toList(),
                          onChanged: loading
                              ? null
                              : (id) {
                                  if (id == null) return;
                                  setState(() {
                                    selectedSite = entrySites.firstWhere((e) => e.id == id);
                                  });
                                },
                        ),
                    ],
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: loading
                          ? null
                          : (controllerMode ? _controllerCheckin : _faceLogin),
                      child: loading
                          ? const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                ),
                                SizedBox(width: 10),
                                Text("Verification..."),
                              ],
                            )
                          : const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.face_retouching_natural_rounded),
                                SizedBox(width: 8),
                                Text("Ouvrir la camera"),
                              ],
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
