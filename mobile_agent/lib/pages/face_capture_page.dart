import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';

/// Autorisation caméra Android via [MainActivity] (évite MissingPluginException
/// après hot restart avec des plugins comme permission_handler).
const MethodChannel _androidCameraPermissionChannel =
    MethodChannel('com.example.mobile_agent/permissions');

class FaceCapturePage extends StatefulWidget {
  const FaceCapturePage({
    super.key,
    required this.title,
    required this.hint,
  });

  final String title;
  final String hint;

  static Future<String?> capture(
    BuildContext context, {
    required String title,
    required String hint,
  }) async {
    return Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => FaceCapturePage(
          title: title,
          hint: hint,
        ),
      ),
    );
  }

  @override
  State<FaceCapturePage> createState() => _FaceCapturePageState();
}

class _FaceCapturePageState extends State<FaceCapturePage> {
  CameraController? _controller;
  FaceDetector? _faceDetector;
  String? _error;
  bool _capturing = false;
  bool _streamRunning = false;
  bool _faceReady = false;
  Size _canvasSize = Size.zero;
  int _frameTick = 0;
  bool _processing = false;
  int _stableGoodFrames = 0;
  bool _cameraDeniedPermanent = false;

  static const Map<DeviceOrientation, int> _orientations = {
    DeviceOrientation.portraitUp: 0,
    DeviceOrientation.landscapeLeft: 90,
    DeviceOrientation.portraitDown: 180,
    DeviceOrientation.landscapeRight: 270,
  };

  @override
  void initState() {
    super.initState();
    _faceDetector = FaceDetector(
      options: FaceDetectorOptions(
        performanceMode: FaceDetectorMode.fast,
        enableLandmarks: false,
        enableContours: false,
        enableClassification: false,
        minFaceSize: 0.12,
      ),
    );
    _initCamera();
  }

  @override
  void dispose() {
    _stopStreamSync();
    _faceDetector?.close();
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _stopStreamSync() async {
    final c = _controller;
    if (c == null || !_streamRunning) return;
    try {
      await c.stopImageStream();
    } catch (_) {
      // déjà arrêté ou caméra en cours de fermeture
    }
    _streamRunning = false;
  }

  Future<bool> _ensureCameraPermission() async {
    if (Platform.isIOS) {
      // iOS : la première ouverture caméra affiche la boîte système (Info.plist).
      return true;
    }
    if (!Platform.isAndroid) {
      return true;
    }
    try {
      final already = await _androidCameraPermissionChannel
          .invokeMethod<bool>('cameraStatus');
      if (already == true) {
        if (mounted) {
          setState(() {
            _cameraDeniedPermanent = false;
            _error = null;
          });
        }
        return true;
      }
      final raw = await _androidCameraPermissionChannel
          .invokeMethod<dynamic>('requestCamera');
      if (!mounted) return false;
      var granted = false;
      var suggestSettings = false;
      if (raw is Map) {
        granted = raw['granted'] == true;
        suggestSettings = raw['suggestSettings'] == true;
      }
      if (granted) {
        setState(() {
          _cameraDeniedPermanent = false;
          _error = null;
        });
        return true;
      }
      setState(() {
        _cameraDeniedPermanent = suggestSettings;
        _error = suggestSettings
            ? "L'accès à la caméra est bloqué. Autorisez la caméra pour SMS Agent dans les paramètres Android."
            : "L'accès à la caméra est nécessaire pour la capture. Appuyez sur Réessayer pour afficher la demande d'autorisation.";
      });
      return false;
    } catch (e, st) {
      debugPrint('Autorisation caméra (channel): $e\n$st');
      if (!mounted) return false;
      setState(() {
        _cameraDeniedPermanent = false;
        _error =
            "Impossible de demander l'autorisation caméra. Réinstallez l'application (arrêt complet du débogage puis flutter run).";
      });
      return false;
    }
  }

  Future<void> _initCamera() async {
    setState(() {
      _error = null;
      _cameraDeniedPermanent = false;
    });
    if (!await _ensureCameraPermission()) {
      return;
    }
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _error = "Aucune caméra disponible.");
        return;
      }
      final selected = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      if (Platform.isAndroid) {
        try {
          await _openCameraWithFormat(selected, ImageFormatGroup.nv21);
          return;
        } catch (e, st) {
          debugPrint('Caméra NV21: $e\n$st');
          await _controller?.dispose();
          if (!mounted) return;
          setState(() => _controller = null);
        }
        await _openCameraWithFormat(selected, ImageFormatGroup.yuv420);
        return;
      }
      await _openCameraWithFormat(selected, ImageFormatGroup.bgra8888);
    } catch (e, st) {
      debugPrint('Caméra: $e\n$st');
      if (!mounted) return;
      setState(() {
        _error =
            "Impossible d'ouvrir la caméra. Si le problème persiste, vérifiez les autorisations et redémarrez l'application.";
      });
    }
  }

  Future<void> _openCameraWithFormat(
    CameraDescription selected,
    ImageFormatGroup imageFormatGroup,
  ) async {
    final controller = CameraController(
      selected,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: imageFormatGroup,
    );
    await controller.initialize();
    if (!mounted) {
      await controller.dispose();
      return;
    }
    setState(() => _controller = controller);
    await _startImageStream();
  }

  Future<void> _startImageStream() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized || _streamRunning) return;
    await c.startImageStream(_onCameraImage);
    _streamRunning = true;
  }

  InputImageRotation? _rotationForImage(CameraController controller) {
    final camera = controller.description;
    final sensorOrientation = camera.sensorOrientation;
    if (Platform.isIOS) {
      return InputImageRotationValue.fromRawValue(sensorOrientation);
    }
    if (Platform.isAndroid) {
      var rotationCompensation =
          _orientations[controller.value.deviceOrientation];
      if (rotationCompensation == null) return null;
      if (camera.lensDirection == CameraLensDirection.front) {
        rotationCompensation = (sensorOrientation + rotationCompensation) % 360;
      } else {
        rotationCompensation =
            (sensorOrientation - rotationCompensation + 360) % 360;
      }
      return InputImageRotationValue.fromRawValue(rotationCompensation);
    }
    return null;
  }

  InputImage? _inputImageFromCameraImage(
    CameraImage image,
    CameraController controller,
  ) {
    final rotation = _rotationForImage(controller);
    if (rotation == null) return null;

    final format = InputImageFormatValue.fromRawValue(image.format.raw);

    if (Platform.isAndroid) {
      if (image.planes.length == 3) {
        final nv21 = _yuv420888ToNv21(image);
        return InputImage.fromBytes(
          bytes: nv21,
          metadata: InputImageMetadata(
            size: Size(image.width.toDouble(), image.height.toDouble()),
            rotation: rotation,
            format: InputImageFormat.nv21,
            bytesPerRow: image.width,
          ),
        );
      }
      if (format == InputImageFormat.nv21 && image.planes.length == 1) {
        final plane = image.planes.first;
        return InputImage.fromBytes(
          bytes: plane.bytes,
          metadata: InputImageMetadata(
            size: Size(image.width.toDouble(), image.height.toDouble()),
            rotation: rotation,
            format: InputImageFormat.nv21,
            bytesPerRow: plane.bytesPerRow,
          ),
        );
      }
      return null;
    }

    if (Platform.isIOS &&
        format != null &&
        format == InputImageFormat.bgra8888) {
      final plane = image.planes.first;
      return InputImage.fromBytes(
        bytes: plane.bytes,
        metadata: InputImageMetadata(
          size: Size(image.width.toDouble(), image.height.toDouble()),
          rotation: rotation,
          format: format,
          bytesPerRow: plane.bytesPerRow,
        ),
      );
    }

    return null;
  }

  /// Fallback si l'appareil renvoie du YUV_420_888 (3 plans) au lieu du NV21.
  Uint8List _yuv420888ToNv21(CameraImage image) {
    final width = image.width;
    final height = image.height;
    final yPlane = image.planes[0];
    final uPlane = image.planes[1];
    final vPlane = image.planes[2];
    final ySize = width * height;
    final out = Uint8List(ySize + (width * height) ~/ 2);
    out.setRange(0, yPlane.bytes.lengthInBytes, yPlane.bytes);

    final uvRowStride = uPlane.bytesPerRow;
    final uvPixelStride = uPlane.bytesPerPixel ?? 1;
    final uBytes = uPlane.bytes;
    final vBytes = vPlane.bytes;
    var o = ySize;
    for (var y = 0; y < height ~/ 2; y++) {
      for (var x = 0; x < width ~/ 2; x++) {
        final uvIndex = x * uvPixelStride + y * uvRowStride;
        if (uvIndex < vBytes.lengthInBytes && uvIndex < uBytes.lengthInBytes) {
          out[o++] = vBytes[uvIndex];
          out[o++] = uBytes[uvIndex];
        }
      }
    }
    return out;
  }

  double _translateX(
    double x,
    Size canvasSize,
    Size imageSize,
    InputImageRotation rotation,
    CameraLensDirection lens,
  ) {
    switch (rotation) {
      case InputImageRotation.rotation90deg:
        return x *
            canvasSize.width /
            (Platform.isIOS ? imageSize.width : imageSize.height);
      case InputImageRotation.rotation270deg:
        return canvasSize.width -
            x *
                canvasSize.width /
                (Platform.isIOS ? imageSize.width : imageSize.height);
      case InputImageRotation.rotation0deg:
      case InputImageRotation.rotation180deg:
        if (lens == CameraLensDirection.back) {
          return x * canvasSize.width / imageSize.width;
        }
        return canvasSize.width - x * canvasSize.width / imageSize.width;
    }
  }

  double _translateY(
    double y,
    Size canvasSize,
    Size imageSize,
    InputImageRotation rotation,
  ) {
    switch (rotation) {
      case InputImageRotation.rotation90deg:
      case InputImageRotation.rotation270deg:
        return y *
            canvasSize.height /
            (Platform.isIOS ? imageSize.height : imageSize.width);
      case InputImageRotation.rotation0deg:
      case InputImageRotation.rotation180deg:
        return y * canvasSize.height / imageSize.height;
    }
  }

  bool _faceAlignedInOval(
    Face face,
    Size canvas,
    Size imageSize,
    InputImageRotation rotation,
    CameraLensDirection lens,
  ) {
    final box = face.boundingBox;
    final left = _translateX(box.left, canvas, imageSize, rotation, lens);
    final top = _translateY(box.top, canvas, imageSize, rotation);
    final right = _translateX(box.right, canvas, imageSize, rotation, lens);
    final bottom = _translateY(box.bottom, canvas, imageSize, rotation);
    final center = Offset((left + right) / 2, (top + bottom) / 2);
    final fw = (right - left).abs();
    final fh = (bottom - top).abs();

    final ovalCenter = Offset(canvas.width / 2, canvas.height * 0.43);
    final ovalW = canvas.width * 0.58;
    final ovalH = canvas.height * 0.42;
    final dx = (center.dx - ovalCenter.dx) / (ovalW / 2);
    final dy = (center.dy - ovalCenter.dy) / (ovalH / 2);
    final inOval = dx * dx + dy * dy <= 1.02;

    final sizeOk =
        fw >= ovalW * 0.38 && fw <= ovalW * 1.12 && fh >= ovalH * 0.35;

    return inOval && sizeOk;
  }

  Future<void> _onCameraImage(CameraImage image) async {
    final c = _controller;
    final detector = _faceDetector;
    if (c == null || !c.value.isInitialized || detector == null) return;
    if (_processing) return;
    _frameTick++;
    if (_frameTick % 2 != 0) return;

    final canvas = _canvasSize;
    if (canvas.isEmpty) return;

    final rotation = _rotationForImage(c);
    if (rotation == null) return;

    final input = _inputImageFromCameraImage(image, c);
    if (input == null) return;

    _processing = true;
    try {
      final faces = await detector.processImage(input);
      if (!mounted) return;

      final imageSize = Size(image.width.toDouble(), image.height.toDouble());
      final lens = c.description.lensDirection;

      var aligned = false;
      if (faces.length == 1) {
        aligned = _faceAlignedInOval(
          faces.first,
          canvas,
          imageSize,
          rotation,
          lens,
        );
      }

      if (aligned) {
        _stableGoodFrames = (_stableGoodFrames + 1).clamp(0, 8);
      } else {
        _stableGoodFrames = 0;
      }
      final ready = _stableGoodFrames >= 3;
      if (ready != _faceReady) {
        setState(() => _faceReady = ready);
      }
    } catch (_) {
      // ignorer une frame défaillante
    } finally {
      _processing = false;
    }
  }

  Future<void> _takePicture() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized || _capturing || !_faceReady) {
      return;
    }
    setState(() => _capturing = true);
    try {
      await _stopStreamSync();
      final shot = await c.takePicture();
      if (!mounted) return;
      Navigator.of(context).pop<String>(shot.path);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = "Capture échouée. Reprenez la photo.";
        _capturing = false;
      });
      await _startImageStream();
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = _controller;
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(widget.title),
      ),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _error!,
                      style: const TextStyle(color: Colors.white),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 20),
                    if (_cameraDeniedPermanent)
                      FilledButton.tonal(
                        onPressed: () async {
                          if (Platform.isAndroid) {
                            try {
                              await _androidCameraPermissionChannel
                                  .invokeMethod<void>('openAppSettings');
                            } catch (e) {
                              debugPrint('openAppSettings: $e');
                            }
                          }
                        },
                        child: const Text("Ouvrir les paramètres"),
                      ),
                    if (_cameraDeniedPermanent) const SizedBox(height: 12),
                    OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white,
                        side: const BorderSide(color: Colors.white54),
                      ),
                      onPressed: () => _initCamera(),
                      child: const Text("Réessayer"),
                    ),
                  ],
                ),
              ),
            )
          : c == null || !c.value.isInitialized
          ? const Center(child: CircularProgressIndicator())
          : LayoutBuilder(
              builder: (context, constraints) {
                final sz = Size(constraints.maxWidth, constraints.maxHeight);
                if (sz != _canvasSize) {
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted) setState(() => _canvasSize = sz);
                  });
                }
                return Stack(
                  fit: StackFit.expand,
                  children: [
                    CameraPreview(c),
                    Positioned.fill(
                      child: IgnorePointer(
                        child: CustomPaint(
                          painter: _FaceOvalOverlayPainter(ready: _faceReady),
                        ),
                      ),
                    ),
                    Positioned(
                      left: 16,
                      right: 16,
                      bottom: 120,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            widget.hint,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.75),
                              fontSize: 13,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _faceReady
                                ? "Prêt — vous pouvez capturer."
                                : "Centrez votre visage dans l'ovale.",
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 32,
                      child: Center(
                        child: FilledButton.icon(
                          onPressed:
                              (_capturing || !_faceReady) ? null : _takePicture,
                          icon: const Icon(Icons.camera_alt_rounded),
                          label: Text(
                            _capturing
                                ? "Capture..."
                                : "Prendre la photo",
                          ),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
    );
  }
}

class _FaceOvalOverlayPainter extends CustomPainter {
  _FaceOvalOverlayPainter({required this.ready});

  final bool ready;

  @override
  void paint(Canvas canvas, Size size) {
    final overlayPaint = Paint()..color = Colors.black.withAlpha(140);
    final center = Offset(size.width / 2, size.height * 0.43);
    final faceRect = Rect.fromCenter(
      center: center,
      width: size.width * 0.58,
      height: size.height * 0.42,
    );

    final overlayPath = Path()
      ..addRect(Rect.fromLTWH(0, 0, size.width, size.height));
    final facePath = Path()..addOval(faceRect);
    final mask = Path.combine(PathOperation.difference, overlayPath, facePath);
    canvas.drawPath(mask, overlayPaint);

    final borderPaint = Paint()
      ..color = ready ? const Color(0xFF4CAF50) : Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawOval(faceRect, borderPaint);
  }

  @override
  bool shouldRepaint(covariant _FaceOvalOverlayPainter oldDelegate) =>
      oldDelegate.ready != ready;
}
