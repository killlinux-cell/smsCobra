import 'assignment.dart';

class FaceIdentifyResult {
  const FaceIdentifyResult({
    required this.guardUsername,
    required this.guardName,
    required this.assignmentId,
    this.assignment,
    this.faceMatchScore,
  });

  final String guardUsername;
  final String guardName;
  final int assignmentId;
  final Assignment? assignment;
  final double? faceMatchScore;
}
