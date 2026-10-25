/// Represents a synthetic Indian citizen profile.
/// All records in Timbre are 100% fictional for prototype safety.
class Citizen {
  final String id;
  final String firstName;
  final String lastName;
  final DateTime dateOfBirth;
  final String gender;
  final String phoneNumber;
  final String state;
  final String district;
  final String pincode;
  final String simulatedIncomeBracket;
  final bool isFictional;

  const Citizen({
    required this.id,
    required this.firstName,
    required this.lastName,
    required this.dateOfBirth,
    required this.gender,
    required this.phoneNumber,
    required this.state,
    required this.district,
    required this.pincode,
    required this.simulatedIncomeBracket,
    this.isFictional = true,
  });

  String get fullName => '$firstName $lastName';

  /// Calculates exact age using calendar year and birthday boundaries (handles leap years correctly).
  static int calculateAge(DateTime dob, [DateTime? referenceDate]) {
    final ref = referenceDate ?? DateTime.now();
    int age = ref.year - dob.year;
    if (ref.month < dob.month ||
        (ref.month == dob.month && ref.day < dob.day)) {
      age--;
    }
    return age;
  }

  int get age => calculateAge(dateOfBirth);

  bool get isAdult => age >= 18;

  Citizen copyWith({
    String? id,
    String? firstName,
    String? lastName,
    DateTime? dateOfBirth,
    String? gender,
    String? phoneNumber,
    String? state,
    String? district,
    String? pincode,
    String? simulatedIncomeBracket,
    bool? isFictional,
  }) {
    return Citizen(
      id: id ?? this.id,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      dateOfBirth: dateOfBirth ?? this.dateOfBirth,
      gender: gender ?? this.gender,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      state: state ?? this.state,
      district: district ?? this.district,
      pincode: pincode ?? this.pincode,
      simulatedIncomeBracket:
          simulatedIncomeBracket ?? this.simulatedIncomeBracket,
      isFictional: isFictional ?? this.isFictional,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'first_name': firstName,
      'last_name': lastName,
      'date_of_birth':
          '${dateOfBirth.year.toString().padLeft(4, '0')}-${dateOfBirth.month.toString().padLeft(2, '0')}-${dateOfBirth.day.toString().padLeft(2, '0')}',
      'gender': gender,
      'phone_number': phoneNumber,
      'state': state,
      'district': district,
      'pincode': pincode,
      'simulated_income_bracket': simulatedIncomeBracket,
      'is_fictional': isFictional,
      'age': age,
    };
  }

  factory Citizen.fromJson(Map<String, dynamic> json) {
    return Citizen(
      id: json['id'] as String,
      firstName: json['first_name'] as String,
      lastName: json['last_name'] as String,
      dateOfBirth: DateTime.parse(json['date_of_birth'] as String),
      gender: json['gender'] as String? ?? 'OTHER',
      phoneNumber: json['phone_number'] as String? ?? '',
      state: json['state'] as String? ?? '',
      district: json['district'] as String? ?? '',
      pincode: json['pincode'] as String? ?? '',
      simulatedIncomeBracket:
          json['simulated_income_bracket'] as String? ?? 'MIDDLE',
      isFictional: json['is_fictional'] as bool? ?? true,
    );
  }
}
