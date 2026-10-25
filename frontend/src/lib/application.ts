import type {
  AccreditationSection,
  ApplicationData,
  ApplicationProgramInput,
  ApplicationType,
  FacultySection,
  FinanceSection,
  InfrastructureSection,
  InstitutionProfileSection,
  NaacGrade,
  NbaStatus,
} from "./api";

export type FieldErrors = Record<string, string>;

export type WizardStepId =
  | "profile"
  | "infrastructure"
  | "faculty"
  | "finance"
  | "accreditation"
  | "programs"
  | "documents"
  | "review";

export interface WizardStep {
  id: WizardStepId;
  label: string;
  description: string;
}

export const WIZARD_STEPS: WizardStep[] = [
  {
    id: "profile",
    label: "Profile",
    description: "Institution identity, address and primary contact.",
  },
  {
    id: "infrastructure",
    label: "Infrastructure",
    description: "Land, buildings, laboratories, library and hostel capacity.",
  },
  {
    id: "faculty",
    label: "Faculty",
    description: "Faculty strength by cadre and the declared ratios.",
  },
  {
    id: "finance",
    label: "Finance",
    description: "Annual fee structure and the declared institutional balance.",
  },
  {
    id: "accreditation",
    label: "Accreditation",
    description: "NAAC and NBA status plus the public mandatory disclosure URL.",
  },
  {
    id: "programs",
    label: "Programmes",
    description: "Programme mix, intake, faculty and laboratory counts.",
  },
  {
    id: "documents",
    label: "Documents",
    description: "Upload the documents required for this application type.",
  },
  {
    id: "review",
    label: "Review",
    description: "Check completeness and submit the application.",
  },
];

export const NAAC_OPTIONS: { value: NaacGrade; label: string }[] = [
  { value: "A++", label: "A++" },
  { value: "A+", label: "A+" },
  { value: "A", label: "A" },
  { value: "B++", label: "B++" },
  { value: "B+", label: "B+" },
  { value: "B", label: "B" },
  { value: "C", label: "C" },
  { value: "NOT_ACCREDITED", label: "Not accredited" },
];

export const NBA_OPTIONS: { value: NbaStatus; label: string }[] = [
  { value: "ACCREDITED", label: "Accredited" },
  { value: "APPLIED", label: "Application submitted" },
  { value: "NOT_ACCREDITED", label: "Not accredited" },
];

export const APPLICATION_TYPE_OPTIONS: { value: ApplicationType; label: string }[] = [
  { value: "NEW_INSTITUTION", label: "New technical institution (Chapter I)" },
  {
    value: "NEW_INSTITUTION_OTHER_REGULATOR",
    label: "Institution approved by another regulator, first AICTE approval",
  },
  {
    value: "CLOSURE_AND_NEW_INSTITUTION",
    label: "Closure plus new institution in the same premises",
  },
  { value: "UNIVERSITY", label: "University (Chapter IV)" },
  { value: "EOA_SELF_DISCLOSURE", label: "Extension of approval based on self-disclosure" },
  { value: "NRI_SEATS", label: "Introduction or continuation of NRI seats" },
  {
    value: "DIPLOMA_DEGREE_CONVERSION",
    label: "Conversion of diploma level into degree level and vice versa",
  },
  { value: "CHANGE_OF_NAME", label: "Change of institution, affiliating body or type name" },
  { value: "NEW_PROGRAMME", label: "Start a new programme or level in an existing institution" },
  {
    value: "MERGER_OF_INSTITUTIONS",
    label: "Merger of institutions under the same or a different trust",
  },
  { value: "EOA_AFTER_BREAK", label: "EoA after a break, restoration of intake or hibernation" },
  { value: "SUPERNUMERARY_FN_OCI", label: "Supernumerary seats for FN, OCI and Gulf children" },
  { value: "INCREASE_INTAKE", label: "Increase in intake or additional course" },
  { value: "INTEGRATED_DUAL_DEGREE", label: "Integrated or dual degree course" },
  { value: "OFF_CAMPUS", label: "Off-campus institution" },
  { value: "FPM", label: "Fellow Programme in Management" },
  {
    value: "COURSE_RENAME_MERGE_REDUCTION",
    label: "Change of course name, merger of courses or reduction in intake",
  },
  { value: "COLLABORATION_TWINNING", label: "Collaboration and twinning programme" },
  { value: "CHANGE_OF_SITE", label: "Change of site or location" },
  { value: "CLOSURE_OF_INSTITUTION", label: "Closure of institution" },
  {
    value: "WOMEN_COED_CONVERSION",
    label: "Conversion of a women's institution into co-ed and vice versa",
  },
  { value: "CLOSURE_OF_PROGRAMME", label: "Closure of a programme or course" },
  { value: "CHANGE_IN_BANK_DETAILS", label: "Change in bank details" },
  {
    value: "CHANGE_OF_TRUST_NAME",
    label: "Change of trust, society or company name or address",
  },
  { value: "EXTENDED_EOA", label: "Extended EoA" },
  { value: "DEEMED_UNIVERSITY_CONVERSION", label: "Institution converted to a deemed university" },
  { value: "ODL_ONLINE", label: "ODL and online courses" },
];

export const PROGRAM_LEVEL_OPTIONS = [
  { value: "UG", label: "Undergraduate (UG)" },
  { value: "PG", label: "Postgraduate (PG)" },
  { value: "DIPLOMA", label: "Diploma" },
  { value: "RESEARCH", label: "Research" },
];

export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
export const DOCUMENT_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PIN_PATTERN = /^\d{6}$/;
const PHONE_PATTERN = /^[0-9+\-()\s]{7,24}$/;

export function currentAcademicYear(): string {
  const now = new Date();
  const start = now.getMonth() >= 5 ? now.getFullYear() : now.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

export function createEmptyProgram(): ApplicationProgramInput {
  return {
    program_name: "",
    level: "UG",
    intake: 60,
    faculty_count: 0,
    lab_count: 0,
  };
}

export function toNumberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : null;
}

export function toIntegerOrNull(value: string): number | null {
  const numeric = toNumberOrNull(value);
  return numeric === null || !Number.isInteger(numeric) ? null : numeric;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function text(value: string | null | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function required(
  errors: FieldErrors,
  key: string,
  value: string,
  label: string,
): boolean {
  if (!value) {
    errors[key] = `${label} is required.`;
    return false;
  }
  return true;
}

export function validateProfile(section: InstitutionProfileSection | null | undefined): FieldErrors {
  const errors: FieldErrors = {};
  required(errors, "head_name", text(section?.head_name), "Head of institution");
  required(errors, "address_line1", text(section?.address_line1), "Address line 1");
  required(errors, "city", text(section?.city), "City");
  required(errors, "state", text(section?.state), "State");
  const pin = text(section?.pin_code);
  if (required(errors, "pin_code", pin, "PIN code") && !PIN_PATTERN.test(pin)) {
    errors.pin_code = "Enter a valid 6-digit PIN code.";
  }
  const email = text(section?.contact_email);
  if (required(errors, "contact_email", email, "Contact email") && !EMAIL_PATTERN.test(email)) {
    errors.contact_email = "Enter a valid email address.";
  }
  const phone = text(section?.contact_phone);
  if (required(errors, "contact_phone", phone, "Contact phone") && !PHONE_PATTERN.test(phone)) {
    errors.contact_phone = "Enter a valid phone number.";
  }
  return errors;
}

function validateNonNegative(
  errors: FieldErrors,
  key: string,
  value: number | null | undefined,
  label: string,
): void {
  if (value === null || value === undefined) {
    errors[key] = `${label} is required.`;
  } else if (value < 0) {
    errors[key] = `${label} cannot be negative.`;
  }
}

export function validateInfrastructure(
  section: InfrastructureSection | null | undefined,
): FieldErrors {
  const errors: FieldErrors = {};
  validateNonNegative(errors, "land_area", section?.land_area, "Land area");
  validateNonNegative(errors, "built_up_area", section?.built_up_area, "Built-up area");
  validateNonNegative(errors, "labs", section?.labs, "Laboratory count");
  validateNonNegative(errors, "library", section?.library, "Library volumes");
  validateNonNegative(errors, "hostel", section?.hostel, "Hostel capacity");
  return errors;
}

export function validateFaculty(section: FacultySection | null | undefined): FieldErrors {
  const errors: FieldErrors = {};
  validateNonNegative(errors, "total", section?.total, "Total faculty");
  validateNonNegative(errors, "professors", section?.professors, "Professors");
  validateNonNegative(
    errors,
    "associate_professors",
    section?.associate_professors,
    "Associate professors",
  );
  validateNonNegative(
    errors,
    "assistant_professors",
    section?.assistant_professors,
    "Assistant professors",
  );
  validateNonNegative(
    errors,
    "student_faculty_ratio",
    section?.student_faculty_ratio,
    "Student-faculty ratio",
  );
  validateNonNegative(errors, "phd_faculty_ratio", section?.phd_faculty_ratio, "Faculty with PhD");
  if (
    section?.phd_faculty_ratio !== null &&
    section?.phd_faculty_ratio !== undefined &&
    section.phd_faculty_ratio > 100
  ) {
    errors.phd_faculty_ratio = "Faculty with PhD cannot exceed 100%.";
  }
  return errors;
}

export function validateFinance(section: FinanceSection | null | undefined): FieldErrors {
  const errors: FieldErrors = {};
  validateNonNegative(errors, "tuition_fee", section?.tuition_fee, "Tuition fee");
  validateNonNegative(errors, "development_fee", section?.development_fee, "Development fee");
  validateNonNegative(errors, "other_fees", section?.other_fees, "Other fees");
  if (section?.balance === null || section?.balance === undefined) {
    errors.balance = "Balance is required.";
  }
  return errors;
}

function validHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateAccreditation(
  section: AccreditationSection | null | undefined,
  disclosureUrl: string | null | undefined,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!section?.naac_grade) {
    errors.naac_grade = "Select a NAAC grade.";
  }
  if (!section?.nba_status) {
    errors.nba_status = "Select the NBA status.";
  }
  const url = text(disclosureUrl);
  if (!url) {
    errors.mandatory_disclosure_url = "Mandatory disclosure URL is required.";
  } else if (!validHttpUrl(url)) {
    errors.mandatory_disclosure_url = "Enter a valid http(s) URL.";
  }
  return errors;
}

export function validateStep(step: WizardStepId, data: ApplicationData): FieldErrors {
  switch (step) {
    case "profile":
      return validateProfile(data.institution_profile);
    case "infrastructure":
      return validateInfrastructure(data.infrastructure);
    case "faculty":
      return validateFaculty(data.faculty);
    case "finance":
      return validateFinance(data.finance);
    case "accreditation":
      return validateAccreditation(data.accreditation, data.mandatory_disclosure_url);
    default:
      return {};
  }
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function firstError(errors: FieldErrors): string | null {
  return Object.values(errors)[0] ?? null;
}

export function stepForChecklistSection(sectionKey: string): WizardStepId {
  switch (sectionKey) {
    case "institution_profile":
      return "profile";
    case "infrastructure":
      return "infrastructure";
    case "faculty":
      return "faculty";
    case "finance":
      return "finance";
    case "accreditation":
    case "mandatory_disclosure_url":
      return "accreditation";
    default:
      return "review";
  }
}

export function stepForMissingCode(code: string): WizardStepId {
  const [section] = code.split(".");
  if (section === "document") {
    return "documents";
  }
  return stepForChecklistSection(section);
}

export function fieldIdForMissingCode(code: string): string {
  const [section, field = ""] = code.split(".");
  if (section === "document") {
    return `document-upload-${field}`;
  }
  const step = stepForChecklistSection(section);
  return `${step}-${field.replaceAll("_", "-")}`;
}

export function programLevelLabel(value: string): string {
  return PROGRAM_LEVEL_OPTIONS.find((option) => option.value === value)?.label ?? value;
}
