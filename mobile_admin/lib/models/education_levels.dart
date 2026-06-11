/// Niveaux d'études — alignés sur `User.EducationLevel` (backend).
class EducationLevelOption {
  const EducationLevelOption(this.value, this.label);

  final String value;
  final String label;
}

const kEducationLevels = <EducationLevelOption>[
  EducationLevelOption('', '— Non renseigné —'),
  EducationLevelOption('non_scolarise', 'Non scolarisé'),
  EducationLevelOption('primaire', 'Primaire'),
  EducationLevelOption('secondaire', 'Secondaire / collège'),
  EducationLevelOption('bepc', 'BEPC'),
  EducationLevelOption('bac', 'Baccalauréat'),
  EducationLevelOption('bac_2', 'BAC+2 (BTS, DUT…)'),
  EducationLevelOption('licence', 'Licence (BAC+3)'),
  EducationLevelOption('master', 'Master (BAC+5)'),
  EducationLevelOption('doctorat', 'Doctorat'),
  EducationLevelOption('autre', 'Autre'),
];
