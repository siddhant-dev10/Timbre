/// Represents a statutory public welfare scheme or government entitlement.
class ServiceScheme {
  final String id;
  final String serviceCode;
  final String serviceName;
  final String administeringBody;
  final String officialPortalUrl;
  final double statutoryFeeInr;
  final String applicationMode; // ONLINE, HYBRID, OFFLINE
  final String descriptionEnglish;
  final String descriptionHinglish;
  final int minAge;
  final int? maxAge;
  final List<String> requiredDocs;

  const ServiceScheme({
    required this.id,
    required this.serviceCode,
    required this.serviceName,
    required this.administeringBody,
    required this.officialPortalUrl,
    required this.statutoryFeeInr,
    required this.applicationMode,
    required this.descriptionEnglish,
    required this.descriptionHinglish,
    required this.minAge,
    this.maxAge,
    required this.requiredDocs,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'service_code': serviceCode,
      'service_name': serviceName,
      'administering_body': administeringBody,
      'official_portal_url': officialPortalUrl,
      'statutory_fee_inr': statutoryFeeInr,
      'application_mode': applicationMode,
      'description_english': descriptionEnglish,
      'description_hinglish': descriptionHinglish,
      'min_age': minAge,
      'max_age': maxAge,
      'required_docs': requiredDocs,
    };
  }

  factory ServiceScheme.fromJson(Map<String, dynamic> json) {
    return ServiceScheme(
      id: json['id'] as String,
      serviceCode: json['service_code'] as String,
      serviceName: json['service_name'] as String,
      administeringBody: json['administering_body'] as String,
      officialPortalUrl: json['official_portal_url'] as String,
      statutoryFeeInr: (json['statutory_fee_inr'] as num?)?.toDouble() ?? 0.0,
      applicationMode: json['application_mode'] as String? ?? 'ONLINE',
      descriptionEnglish: json['description_english'] as String? ?? '',
      descriptionHinglish: json['description_hinglish'] as String? ?? '',
      minAge: json['min_age'] as int? ?? 18,
      maxAge: json['max_age'] as int?,
      requiredDocs:
          (json['required_docs'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
    );
  }
}
