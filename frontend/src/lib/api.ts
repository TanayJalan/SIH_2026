const configuredBaseUrl = import.meta.env.VITE_API_URL;
export const API_BASE_URL = (configuredBaseUrl ?? "http://localhost:8000").replace(/\/$/, "");

export type Role =
  | "INSTITUTION_ADMIN"
  | "REGULATION_BUREAU_OFFICER"
  | "SCRUTINY_COMMITTEE_MEMBER"
  | "EVC_MEMBER"
  | "REGIONAL_OFFICER"
  | "SHC_MEMBER"
  | "SAC_MEMBER"
  | "EXECUTIVE_COMMITTEE_MEMBER"
  | "COMPLAINT_SCRUTINY_MEMBER"
  | "SUPER_ADMIN";

export type ApplicationType =
  | "NEW_INSTITUTION"
  | "NEW_INSTITUTION_OTHER_REGULATOR"
  | "CLOSURE_AND_NEW_INSTITUTION"
  | "UNIVERSITY"
  | "EOA_SELF_DISCLOSURE"
  | "NRI_SEATS"
  | "DIPLOMA_DEGREE_CONVERSION"
  | "CHANGE_OF_NAME"
  | "NEW_PROGRAMME"
  | "MERGER_OF_INSTITUTIONS"
  | "EOA_AFTER_BREAK"
  | "SUPERNUMERARY_FN_OCI"
  | "INCREASE_INTAKE"
  | "INTEGRATED_DUAL_DEGREE"
  | "OFF_CAMPUS"
  | "FPM"
  | "COURSE_RENAME_MERGE_REDUCTION"
  | "COLLABORATION_TWINNING"
  | "CHANGE_OF_SITE"
  | "CLOSURE_OF_INSTITUTION"
  | "WOMEN_COED_CONVERSION"
  | "CLOSURE_OF_PROGRAMME"
  | "CHANGE_IN_BANK_DETAILS"
  | "CHANGE_OF_TRUST_NAME"
  | "EXTENDED_EOA"
  | "DEEMED_UNIVERSITY_CONVERSION"
  | "ODL_ONLINE";

export type ApplicationTrack = "NEW_INSTITUTION" | "EXISTING" | "UNIVERSITY" | "ODL";

export type ApplicationCategory = "CAT1_CUTOFF" | "CAT2_YEAR_ROUND";

export type DecisionType = "LOA" | "EOA" | "LOD" | "LOR";

/**
 * Every state the backend can return.
 *
 * The APH state machine emits the Track A-D values; the block below the
 * "legacy" comment was produced by the pre-APH linear workflow and is kept
 * read-only so historical rows and events still render.
 */
export type ApplicationStatus =
  // Track A (Chapter I: new institution, extension of approval).
  | "DRAFT"
  | "SUBMITTED"
  | "SCRUTINY"
  | "DEFICIENCY_COMMUNICATED"
  | "INSTITUTION_COMPLIANCE"
  | "RE_SCRUTINY"
  | "EVC_CONSTITUTED"
  | "EVC_DONE"
  | "REGULATION_BUREAU_OBSERVATIONS"
  | "EC_DECISION"
  | "COUNCIL_RATIFICATION"
  | "LOA_ISSUED"
  | "LOD_ISSUED"
  | "LOR_ISSUED"
  | "APPEAL_WINDOW"
  | "SAC_REVIEW"
  | "COUNCIL_FINAL"
  | "REGIONAL_ENDORSEMENT"
  | "FINAL_LOA"
  | "FINAL_LOD"
  | "FINAL_LOR"
  | "SECURITY_DEPOSIT_PENDING"
  | "ACTIVE_LOA"
  | "CANCELLED"
  | "WITHDRAWN"
  // Track B (extension of approval by self-disclosure).
  | "SELF_DISCLOSURE_CHECK"
  | "RANDOM_EVC"
  | "COMPLIANCE_WINDOW"
  | "EC_LISTING"
  | "EOA_ISSUED"
  | "SPEAKING_ORDER"
  | "ACTIVE_EOA"
  // Track C / D (existing-institution changes).
  | "SHC_HEARING"
  | "CLOSED"
  // Legacy pre-APH values (read-only for historical rows).
  | "DOCUMENT_VERIFICATION"
  | "DEFICIENCY_RAISED"
  | "DEFICIENCY_RESPONDED"
  | "INSPECTION_SCHEDULED"
  | "INSPECTION_DONE"
  | "COMMITTEE_REVIEW"
  | "APPROVED"
  | "REJECTED";

export type WorkflowStage =
  | "APPLICATION"
  | "DOCUMENT_VERIFICATION"
  | "SCRUTINY"
  | "DEFICIENCY"
  | "INSPECTION"
  | "COMMITTEE_REVIEW"
  | "DECISION"
  | "COMPLETED";

export type WorkflowAction =
  | "submit"
  | "pay_ter"
  | "assign_scrutiny"
  | "scrutiny_recommend"
  | "communicate_deficiency"
  | "submit_compliance"
  | "re_scrutiny_verify"
  | "constitute_evc"
  | "submit_evc_video"
  | "evc_report"
  | "observations"
  | "list_for_ec"
  | "ec_decide"
  | "council_ratification"
  | "issue_letter"
  | "issue_loa"
  | "issue_eoa"
  | "issue_lod"
  | "issue_lor"
  | "file_appeal"
  | "sac_recommend"
  | "send_back"
  | "council_final"
  | "endorse_decision"
  | "pay_security_deposit"
  | "apply_deposit_penalty"
  | "finalize_no_appeal"
  | "expire_loa"
  | "shc_hearing"
  | "run_self_disclosure_check"
  | "reopen_once"
  | "withdraw_application";

export interface InstitutionSummary {
  id: string;
  name: string;
  state: string;
  region: string;
}

export interface OfficerSummary {
  id: string;
  name: string;
  email: string;
  role: Role;
}

/**
 * Outcome recorded against a decision.
 *
 * ``RECOMMEND``/``NOT_RECOMMEND``/``SEND_BACK`` cover SAC and SHC
 * recommendations; the letter outcomes cover EC and Council decisions.
 */
export type DecisionOutcome =
  | "LOA"
  | "EOA"
  | "LOD"
  | "LOR"
  | "RECOMMEND"
  | "NOT_RECOMMEND"
  | "SEND_BACK";

export interface ApplicationDecision {
  /** Legacy decision payload; prefer the decision letters API. */
  outcome: string;
  decided_by: string;
  decided_by_name: string;
  decided_at: string;
  comment: string | null;
  conditions: string | null;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: Role;
  institution_id: string | null;
  institution: InstitutionSummary | null;
  region: string | null;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserProfile;
}

export interface PublicDemoAccount {
  role: Role;
  label: string;
  email: string;
  password: string;
}

export interface PublicStats {
  applications_in_progress: number;
  average_days_to_decision: number | null;
  institutions_needing_attention: number;
  demo_mode: boolean;
  demo_accounts: PublicDemoAccount[];
  as_of: string;
}

export interface ApplicationRecord {
  id: string;
  reference: string | null;
  institution_id: string;
  institution: InstitutionSummary;
  track: ApplicationTrack;
  application_type: ApplicationType;
  category: ApplicationCategory;
  portal_application_no: string | null;
  academic_year: string;
  status: ApplicationStatus;
  current_stage: WorkflowStage;
  assigned_officer_id: string | null;
  submitted_at: string | null;
  stage_entered_at: string | null;
  sla_due_at: string | null;
  is_withdrawn: boolean;
  is_escalated: boolean;
  locked_at: string | null;
  reopen_count: number;
  late_submission: boolean;
  ter_amount_paise: number | null;
  ter_paid_at: string | null;
  ter_receipt_no: string | null;
  decision_type: DecisionType | null;
  decision_uploaded_at: string | null;
  appeal_deadline: string | null;
  risk_score: string | number | null;
  compliance_score: string | number | null;
  created_at: string;
  updated_at: string;
}

export interface InstitutionProfileSection {
  head_name?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  pin_code?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  website?: string | null;
}

export interface InfrastructureSection {
  land_area?: number | null;
  built_up_area?: number | null;
  labs?: number | null;
  library?: number | null;
  hostel?: number | null;
}

export interface FacultySection {
  total?: number | null;
  professors?: number | null;
  associate_professors?: number | null;
  assistant_professors?: number | null;
  student_faculty_ratio?: number | null;
  phd_faculty_ratio?: number | null;
}

export interface FinanceSection {
  tuition_fee?: number | null;
  development_fee?: number | null;
  other_fees?: number | null;
  balance?: number | null;
}

export type NaacGrade =
  | "A++"
  | "A+"
  | "A"
  | "B++"
  | "B+"
  | "B"
  | "C"
  | "NOT_ACCREDITED";

export type NbaStatus = "ACCREDITED" | "NOT_ACCREDITED" | "APPLIED";

export interface AccreditationSection {
  naac_grade?: NaacGrade | null;
  nba_status?: NbaStatus | null;
  last_validated_on?: string | null;
}

export interface ApplicationData {
  institution_profile?: InstitutionProfileSection | null;
  infrastructure?: InfrastructureSection | null;
  faculty?: FacultySection | null;
  finance?: FinanceSection | null;
  accreditation?: AccreditationSection | null;
  mandatory_disclosure_url?: string | null;
}

export interface ApplicationProgram {
  id: string;
  application_id: string;
  program_name: string;
  level: string;
  intake: number;
  faculty_count: number;
  lab_count: number;
}

export interface ApplicationDetail extends ApplicationRecord {
  data: ApplicationData;
  programs: ApplicationProgram[];
  assigned_officer: OfficerSummary | null;
  decision: ApplicationDecision | null;
}

export interface ApplicationProgramInput {
  program_name: string;
  level: string;
  intake: number;
  faculty_count: number;
  lab_count: number;
}

export type DocumentVerificationStatus =
  | "PENDING"
  | "VERIFIED"
  | "FLAGGED"
  | "REJECTED";

export interface DocumentRecord {
  id: string;
  application_id: string;
  doc_type: string;
  doc_code: string | null;
  signed_with_dsc: boolean;
  filename: string;
  content_type: string;
  size_bytes: number;
  version: number;
  verification_status: DocumentVerificationStatus;
  verification_reason: string | null;
  uploaded_by: string;
  created_at: string;
  download_url: string;
}

export interface ChecklistDocument {
  doc_type: string;
  doc_code: string | null;
  label: string;
  mandatory: boolean;
  uploaded: boolean;
  document_id: string | null;
  filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  version: number | null;
  signed_with_dsc: boolean | null;
  verification_status: DocumentVerificationStatus | null;
  verification_reason: string | null;
  uploaded_at: string | null;
  download_url: string | null;
}

export interface DocumentChecklist {
  application_id: string;
  documents: ChecklistDocument[];
  required_count: number;
  uploaded_count: number;
  percentage: number;
}

export interface ChecklistSection {
  key: string;
  label: string;
  complete: boolean;
  missing_fields: string[];
}

export interface MissingItem {
  code: string;
  section: string;
  message: string;
}

export interface ApplicationChecklist {
  application_id: string;
  sections: ChecklistSection[];
  documents: ChecklistDocument[];
  required_items: number;
  completed_items: number;
  percentage: number;
  can_submit: boolean;
  missing: MissingItem[];
}

export interface FeeLine {
  item_code: string;
  label: string;
  unit: string;
  units: number;
  unit_amount_paise: number;
  amount_paise: number;
  apH_clause: string;
  needs_verification: boolean;
}

export interface FeeQuote {
  application_id: string;
  application_no: string | null;
  academic_year: string;
  institution_class: string;
  currency: string;
  lines: FeeLine[];
  total_paise: number;
  paid_paise: number;
  refunded_paise: number;
  due_paise: number;
  is_paid: boolean;
  late_submission: boolean;
  ter_receipt_no: string | null;
  ter_paid_at: string | null;
  payment_required_for_submission: boolean;
  notes: string[];
}

export type FeeKind = "TER" | "PENALTY" | "REFUND" | "DEDUCTION";

export interface FeeTransaction {
  id: string;
  application_id: string;
  item_code: string;
  amount_paise: number;
  kind: FeeKind;
  receipt_no: string | null;
  paid_at: string | null;
  apH_clause: string;
  needs_verification: boolean;
}

export interface FeePaymentResult {
  quote: FeeQuote;
  transactions: FeeTransaction[];
}

export type RefundReason =
  | "SCRUTINY_REJECTED_NO_APPEAL"
  | "REVOKED_AFTER_PAYMENT"
  | "EXCESS_PAYMENT";

export interface RefundResult {
  transaction: FeeTransaction;
  refundable_paise: number;
  retained_paise: number;
  note: string;
}

export interface SecurityDepositLine {
  programme_family: string;
  level: string;
  base_paise: number;
  leased: boolean;
  deposit_paise: number;
  penalty_percent: number;
  total_due_paise: number;
  apH_clause: string;
  needs_verification: boolean;
}

export interface SecurityDepositQuote {
  application_id: string;
  as_of: string;
  intimation_on: string | null;
  lines: SecurityDepositLine[];
  total_base_paise: number;
  total_due_paise: number;
  penalty_windows: string;
  notes: string[];
}

export interface RouteStep {
  key: string;
  label: string;
  applies: boolean;
  description: string;
  apH_clause: string;
}

export interface RouteDocument {
  doc_code: string | null;
  doc_type: string;
  label: string;
  mandatory: boolean;
  condition_expr: string | null;
  apH_clause: string;
  needs_verification: boolean;
}

export interface ApplicationTypeRouteSummary {
  type: ApplicationType;
  label: string;
  category: ApplicationCategory;
  year_round: boolean;
  cutoff_applies: boolean;
  cutoff_on: string | null;
  steps: RouteStep[];
  required_documents: RouteDocument[];
  ter_item_code: string | null;
  ter_label: string | null;
  ter_unit: string | null;
  ter_unit_amount_paise: number | null;
  ter_note: string;
  apH_clause: string;
  needs_verification: boolean;
}

export interface DeficiencyReportItem {
  code: string;
  name: string;
  category: string;
  severity: Severity;
  status: ComplianceRuleStatus;
  message: string;
  apH_clause: string;
  needs_verification: boolean;
  observed_value: number | null;
  explanation: Record<string, unknown>;
}

export interface DeficiencyReport {
  application_id: string;
  application_no: string | null;
  academic_year: string;
  generated_at: string;
  nil_deficiency: boolean;
  banner: string;
  items: DeficiencyReportItem[];
  passed_count: number;
  failed_count: number;
  not_assessed_count: number;
  score: number;
  status: ComplianceOutcome;
  include_not_assessed: boolean;
  apH_clause: string;
}

export interface ReopenResult {
  application_id: string;
  reopen_count: number;
  status: ApplicationStatus;
  quote: FeeQuote;
  transactions: FeeTransaction[];
  message: string;
}

export type ComplianceRuleStatus = "PASS" | "FAIL" | "NOT_ASSESSED";
export type ComplianceOutcome = "PASS" | "ATTENTION" | "INCOMPLETE";

export interface ComplianceRulePreview {
  code: string;
  name: string;
  category: string;
  description: string;
  severity: Severity;
  metric_key: string;
  operator: string;
  threshold: number;
  unit: string | null;
  observed_value: number | null;
  status: ComplianceRuleStatus;
  message: string;
}

export interface CompliancePreview {
  application_id: string;
  evaluated_at: string;
  rules: ComplianceRulePreview[];
  passed_count: number;
  failed_count: number;
  not_assessed_count: number;
  assessed_count: number;
  score: number;
  outcome: ComplianceOutcome;
  status: ComplianceHealth;
}

export type ComplianceHealth = "GREEN" | "AMBER" | "RED";
export type RuleOperator =
  | "<"
  | "<="
  | ">="
  | ">"
  | "="
  | "=="
  | "!="
  | "BETWEEN"
  | "EXISTS";

export interface ComplianceRule {
  id: string;
  code: string;
  name: string;
  category: string;
  description: string;
  metric_key: string;
  operator: RuleOperator;
  threshold: number;
  threshold_max: number | null;
  severity: Severity;
  applies_to: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ComplianceRulePage {
  items: ComplianceRule[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComplianceRuleInput {
  code: string;
  name: string;
  category: string;
  description: string;
  metric_key: string;
  operator: RuleOperator;
  threshold: number;
  threshold_max: number | null;
  severity: Severity;
  applies_to: string;
  is_active: boolean;
}

export interface ComplianceMetric {
  key: string;
  label: string;
  unit: string | null;
}

export interface RuleImpactInstitution {
  institution_id: string;
  institution_name: string;
  region: string;
  current_status: ComplianceHealth;
  projected_status: ComplianceHealth;
}

export interface ComplianceRuleImpact {
  red_flips: number;
  amber_flips: number;
  improved: number;
  unchanged: number;
  affected: RuleImpactInstitution[];
  message: string;
}

export interface ComplianceMonitorItem {
  institution_id: string;
  institution_name: string;
  region: string;
  state: string;
  latest_score: number | null;
  latest_status: ComplianceHealth | null;
  latest_failed_count: number | null;
  latest_missing_count: number | null;
  latest_evaluated_at: string | null;
  latest_trigger: string | null;
  application_id: string | null;
  application_reference: string | null;
}

export interface ComplianceMonitorPage {
  items: ComplianceMonitorItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComplianceTrendPoint {
  snapshot_id: string;
  score: number;
  status: ComplianceHealth;
  failed_count: number;
  missing_count: number;
  trigger: string;
  evaluated_at: string;
  application_id: string | null;
}

export interface ComplianceInstitutionTrend {
  institution_id: string;
  institution_name: string;
  region: string;
  points: ComplianceTrendPoint[];
}

export interface SeverityWeights {
  CRITICAL: number;
  HIGH: number;
  MEDIUM: number;
  LOW: number;
}

export interface RagBreakpoints {
  red_below: number;
  amber_below: number;
}

export interface ComplianceConfig {
  severity_weights: SeverityWeights;
  rag_breakpoints: RagBreakpoints;
  updated_at: string | null;
}

export interface ComplianceConfigUpdate {
  severity_weights?: SeverityWeights;
  rag_breakpoints?: RagBreakpoints;
}

export interface ComplianceMonitorRun {
  evaluated: number;
  red: number;
  amber: number;
  green: number;
  message: string;
}

export interface ApplicationSubmission {
  application: ApplicationDetail;
  submitted_at: string;
  sla_due_at: string;
  message: string;
}

export type DeficiencyStatus = "OPEN" | "RESPONDED" | "CLOSED";
export type InspectionStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";
export type InspectionRecommendation = "APPROVE" | "DEFICIENCY" | "REJECT";

export type AllowedActionRequirement =
  | "none"
  | "deficiencies"
  | "responses"
  | "deficiency_id"
  | "inspection_schedule"
  | "inspection_report"
  | "video"
  | "decision"
  | "shc_outcome"
  | "deposit";

export interface AllowedAction {
  action: WorkflowAction;
  label: string;
  description: string;
  requires: AllowedActionRequirement;
  tone: "primary" | "secondary" | "danger";
}

export interface AllowedActionsResponse {
  application_id: string;
  status: ApplicationStatus;
  current_stage: WorkflowStage;
  is_withdrawn: boolean;
  actions: AllowedAction[];
}

/** One configured state of a workflow definition (read-only reference data). */
export interface WorkflowStateDefinition {
  code: ApplicationStatus;
  label: string;
  stage: WorkflowStage;
  is_initial: boolean;
  is_terminal: boolean;
  sort_order: number;
  description: string;
  apH_clause: string;
  needs_verification: boolean;
}

/** One legal edge of a workflow definition (read-only reference data). */
export interface WorkflowTransitionDefinition {
  from_state: ApplicationStatus;
  to_state: ApplicationStatus;
  action: string;
  label: string;
  description: string;
  allowed_roles: Role[];
  guard_expr: string[];
  side_effects: string[];
  requires: AllowedActionRequirement;
  tone: string;
  sla_stage: WorkflowStage | null;
  priority: number;
  apH_clause: string;
  needs_verification: boolean;
}

/**
 * The configured workflow for an application type. The case file reads its
 * stages from here instead of hard-coding the APH pipeline.
 */
export interface WorkflowDefinition {
  key: string;
  label: string;
  track: string;
  description: string;
  config: Record<string, unknown>;
  apH_clause: string;
  needs_verification: boolean;
  states: WorkflowStateDefinition[];
  transitions: WorkflowTransitionDefinition[];
}

export interface WorkflowEventRecord {
  id: string;
  application_id: string;
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  action: WorkflowAction | null;
  actor_id: string | null;
  actor_name: string | null;
  comment: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface WorkflowTimeline {
  application_id: string;
  status: ApplicationStatus;
  current_stage: WorkflowStage;
  stage_entered_at: string | null;
  sla_due_at: string | null;
  is_withdrawn: boolean;
  is_escalated: boolean;
  events: WorkflowEventRecord[];
}

export interface DeficiencyRecord {
  id: string;
  application_id: string;
  category: string;
  description: string;
  status: DeficiencyStatus;
  due_date: string;
  raised_by: string;
  raised_by_name: string | null;
  response_text: string | null;
  response_document_id: string | null;
  response_document_filename: string | null;
  responded_at: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface InspectionReport {
  infrastructure_ok: boolean;
  faculty_verified: boolean;
  lab_verified: boolean;
  observations: string;
  recommendation: InspectionRecommendation;
}

export interface InspectionRecord {
  id: string;
  application_id: string;
  committee_id: string;
  committee_name: string | null;
  scheduled_on: string;
  status: InspectionStatus;
  report: InspectionReport | null;
  recommendation: string | null;
  created_at: string;
}

export interface CommitteeMember {
  id: string;
  name: string;
  email: string;
  role: Role;
  region: string | null;
}

export interface DeficiencyInput {
  category: string;
  description: string;
  due_date: string;
}

export interface DeficiencyResponseInput {
  deficiency_id: string;
  response_text: string;
  document_id?: string;
}

export interface WorkflowActionPayload {
  comment?: string;
  officer_id?: string;
  deficiencies?: DeficiencyInput[];
  responses?: DeficiencyResponseInput[];
  deficiency_id?: string;
  committee_id?: string;
  scheduled_on?: string;
  evc_mode?: string;
  report?: InspectionReport;
  // Expert Visit Committee evidence (APH 1.9f-g).
  video_url?: string;
  video_minutes?: number;
  // Regulation Bureau, EC, SAC and Council decisions.
  notes?: string;
  observations?: string;
  decision?: DecisionOutcome;
  sac_recommendation?: DecisionOutcome;
  shc_outcome?: DecisionOutcome;
  quorum_met?: boolean;
  speaking_order?: string;
  // Security Deposit and Affidavit 3 (APH 2.25f).
  deposit_receipt_no?: string;
  affidavit3_filed?: boolean;
  // Appeals and track-specific facts.
  appeal_text?: string;
  approved_intake?: number;
  random_evc?: boolean;
  closure_failed?: boolean;
  pending_court_case?: boolean;
  charge_sheet_pending?: boolean;
}

export interface WorkflowActionResult {
  application: ApplicationDetail;
  events: WorkflowEventRecord[];
  message: string;
}

export interface ApplicationQuery {
  page?: number;
  pageSize?: number;
  overdue?: boolean;
  institutionId?: string;
  assignedToMe?: boolean;
  sort?: "recent" | "due";
}

export interface SearchApplicationResult {
  id: string;
  reference: string | null;
  institution_name: string;
  status: ApplicationStatus;
  academic_year: string;
}

export interface SearchInstitutionResult {
  id: string;
  name: string;
  state: string;
  region: string;
}

export interface SearchPageResult {
  label: string;
  path: string;
}

export interface SearchResponse {
  query: string;
  applications: SearchApplicationResult[];
  institutions: SearchInstitutionResult[];
  pages: SearchPageResult[];
}

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertChannel = "IN_APP" | "EMAIL" | "SMS";
export type AlertStatus = "PENDING" | "SENT" | "READ" | "ACKED";
export type AlertTrigger =
  | "DEADLINE_APPROACHING"
  | "SLA_BREACHED"
  | "DEFICIENCY_DUE"
  | "DEFICIENCY_OVERDUE"
  | "DOCUMENT_EXPIRING"
  | "COMPLIANCE_RED"
  | "APPLICATION_STATUS_CHANGED"
  | "INSPECTION_SCHEDULED";

export interface AlertRecord {
  id: string;
  application_id: string | null;
  rule_id: string | null;
  parent_alert_id: string | null;
  type: string;
  severity: Severity;
  title: string;
  message: string;
  channel: AlertChannel;
  status: AlertStatus;
  escalation_level: number;
  sent_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by_id: string | null;
  created_at: string;
}

export interface AlertQuery {
  page?: number;
  pageSize?: number;
  unread?: boolean;
  status?: AlertStatus;
  severity?: Severity;
  type?: string;
  applicationId?: string;
}

export interface AlertSummary {
  total: number;
  unread: number;
  acknowledged: number;
  by_severity: Record<Severity, number>;
  unread_by_severity: Record<Severity, number>;
}

export interface AlertRule {
  id: string;
  code: string;
  name: string;
  description: string;
  trigger_type: AlertTrigger;
  days_before: number;
  severity: Severity;
  channel_list: AlertChannel[];
  template: string;
  escalation_role: Role;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AlertRulePage {
  items: AlertRule[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertRuleInput {
  code: string;
  name: string;
  description: string;
  trigger_type: AlertTrigger;
  days_before: number;
  severity: Severity;
  channel_list: AlertChannel[];
  template: string;
  escalation_role: Role;
  is_active: boolean;
}

export interface AlertScanSummary {
  alerts_created: number;
  escalations: number;
  notifications_sent: number;
  scanned_through: string;
}

export interface TimeSimulation {
  enabled: boolean;
  simulated_now: string;
  real_now: string;
  offset_days: number;
  scan: AlertScanSummary | null;
}

export interface TimeSimulationUpdate {
  days?: number;
  reset?: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AuditActor {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface AuditLogRecord {
  id: string;
  actor_id: string | null;
  actor: AuditActor | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

export interface AuditLogQuery {
  page?: number;
  pageSize?: number;
  entityType?: string;
  entityId?: string;
  actorId?: string;
  startDate?: string;
  endDate?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly missing: MissingItem[] | null;

  constructor(status: number, message: string, detail?: unknown, missing?: MissingItem[] | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail ?? null;
    this.missing = missing ?? null;
  }
}

type QueryValue = string | number | null | undefined;

function withQuery(path: string, params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function readErrorDetail(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter((item): item is string => item !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  if (
    typeof detail === "object" &&
    detail !== null &&
    "message" in detail &&
    typeof (detail as { message: unknown }).message === "string"
  ) {
    return (detail as { message: string }).message;
  }
  return null;
}

function readMissingItems(payload: unknown): MissingItem[] | null {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (
    typeof detail !== "object" ||
    detail === null ||
    !("missing" in detail) ||
    !Array.isArray((detail as { missing: unknown }).missing)
  ) {
    return null;
  }
  return (detail as { missing: MissingItem[] }).missing;
}

function buildApiError(status: number, payload: unknown): ApiError {
  return new ApiError(
    status,
    readErrorDetail(payload) ?? `Request failed with status ${status}`,
    payload,
    readMissingItems(payload),
  );
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  token?: string | null;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "The API is unreachable. Check that the backend is running.");
  }

  const contentType = response.headers.get("content-type");
  const payload: unknown =
    response.status === 204
      ? null
      : contentType?.includes("application/json")
        ? await response.json()
        : null;

  if (!response.ok) {
    if (response.status === 401 && options.token && path !== "/auth/me") {
      window.dispatchEvent(new Event("aicte:unauthorized"));
    }
    throw buildApiError(response.status, payload);
  }

  return payload as T;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function getPublicStats(): Promise<PublicStats> {
  return request<PublicStats>("/public/stats");
}

export function getMe(token: string): Promise<UserProfile> {
  return request<UserProfile>("/auth/me", { token });
}

export function getApplications(
  token: string,
  query: ApplicationQuery = {},
): Promise<Page<ApplicationRecord>> {
  return request<Page<ApplicationRecord>>(
    withQuery("/applications", {
      page: query.page ?? 1,
      page_size: query.pageSize ?? 10,
      overdue: query.overdue ? "true" : undefined,
      institution_id: query.institutionId,
      assigned_to_me: query.assignedToMe ? "true" : undefined,
      sort: query.sort,
    }),
    { token },
  );
}

export function getApplication(
  token: string,
  applicationId: string,
): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/applications/${applicationId}`, { token });
}

export interface ApplicationCreateInput {
  application_type: ApplicationType;
  academic_year: string;
  track?: ApplicationTrack;
  category?: ApplicationCategory;
}

export function createApplication(
  token: string,
  input: ApplicationCreateInput,
): Promise<ApplicationDetail> {
  return request<ApplicationDetail>("/applications", {
    method: "POST",
    token,
    body: input,
  });
}

export function updateApplicationData(
  token: string,
  applicationId: string,
  data: ApplicationData,
): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/applications/${applicationId}`, {
    method: "PATCH",
    token,
    body: { data },
  });
}

export function deleteApplication(token: string, applicationId: string): Promise<void> {
  return request<void>(`/applications/${applicationId}`, {
    method: "DELETE",
    token,
  });
}

export function getApplicationChecklist(
  token: string,
  applicationId: string,
): Promise<ApplicationChecklist> {
  return request<ApplicationChecklist>(`/applications/${applicationId}/checklist`, { token });
}

export function getDocumentChecklist(
  token: string,
  applicationId: string,
): Promise<DocumentChecklist> {
  return request<DocumentChecklist>(
    `/applications/${applicationId}/documents/checklist`,
    { token },
  );
}

export function getApplicationTypeRoutes(
  token: string,
  academicYear?: string,
): Promise<ApplicationTypeRouteSummary[]> {
  const query = academicYear
    ? `?academic_year=${encodeURIComponent(academicYear)}`
    : "";
  return request<ApplicationTypeRouteSummary[]>(
    `/applications/type-routes${query}`,
    { token },
  );
}

export function getApplicationFee(
  token: string,
  applicationId: string,
  options: { extraScrutiny?: boolean; extraEvcMode?: "ONLINE" | "PHYSICAL" } = {},
): Promise<FeeQuote> {
  const params = new URLSearchParams();
  if (options.extraScrutiny) {
    params.set("extra_scrutiny", "true");
  }
  if (options.extraEvcMode) {
    params.set("extra_evc_mode", options.extraEvcMode);
  }
  const query = params.toString();
  return request<FeeQuote>(
    `/applications/${applicationId}/fee${query ? `?${query}` : ""}`,
    { token },
  );
}

export function payApplicationFee(
  token: string,
  applicationId: string,
): Promise<FeePaymentResult> {
  return request<FeePaymentResult>(`/applications/${applicationId}/fee/pay`, {
    method: "POST",
    token,
    body: { payment_method: "SIMULATED", confirm: true },
  });
}

export function refundApplicationFee(
  token: string,
  applicationId: string,
  reason: RefundReason,
  note?: string,
): Promise<RefundResult> {
  return request<RefundResult>(`/applications/${applicationId}/fee/refund`, {
    method: "POST",
    token,
    body: { reason, note },
  });
}

export function getSecurityDepositQuote(
  token: string,
  applicationId: string,
): Promise<SecurityDepositQuote> {
  return request<SecurityDepositQuote>(
    `/applications/${applicationId}/security-deposit-quote`,
    { token },
  );
}

export function reopenApplication(
  token: string,
  applicationId: string,
  input: {
    reason: string;
    trust_resolution_reference?: string;
    late_penalty_acknowledged?: boolean;
  },
): Promise<ReopenResult> {
  return request<ReopenResult>(`/applications/${applicationId}/reopen`, {
    method: "POST",
    token,
    body: {
      late_penalty_acknowledged: true,
      ...input,
    },
  });
}

export function getDeficiencyReport(
  token: string,
  applicationId: string,
  includeNotAssessed = true,
): Promise<DeficiencyReport> {
  return request<DeficiencyReport>(
    `/applications/${applicationId}/deficiency-report?include_not_assessed=${includeNotAssessed}`,
    { token },
  );
}

export function listDocumentShells(
  token: string,
  applicationId: string,
): Promise<Record<string, string>> {
  return request<Record<string, string>>(
    `/applications/${applicationId}/document-shells`,
    { token },
  );
}

export async function downloadDocumentShell(
  token: string,
  applicationId: string,
  docCode: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/applications/${applicationId}/document-shells/${docCode}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    const text = await response.text();
    let payload: unknown = null;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
    throw buildApiError(response.status, payload);
  }
  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = objectUrl;
  link.download = `${docCode.toLowerCase()}.html`;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 0);
}

export function listApplicationDocuments(
  token: string,
  applicationId: string,
): Promise<DocumentRecord[]> {
  return request<DocumentRecord[]>(`/applications/${applicationId}/documents`, { token });
}

export function getCompliancePreview(
  token: string,
  applicationId: string,
  data: ApplicationData,
): Promise<CompliancePreview> {
  return request<CompliancePreview>(`/applications/${applicationId}/compliance/preview`, {
    method: "POST",
    token,
    body: { data },
  });
}

export function getApplicationCompliance(
  token: string,
  applicationId: string,
): Promise<CompliancePreview> {
  return request<CompliancePreview>(`/applications/${applicationId}/compliance`, {
    token,
  });
}

export function listComplianceRules(
  token: string,
  options: { includeInactive?: boolean; page?: number; pageSize?: number } = {},
): Promise<ComplianceRulePage> {
  const params = new URLSearchParams({
    include_inactive: String(options.includeInactive ?? true),
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 100),
  });
  return request<ComplianceRulePage>(`/compliance/rules?${params.toString()}`, { token });
}

export function createComplianceRule(
  token: string,
  input: ComplianceRuleInput,
): Promise<ComplianceRule> {
  return request<ComplianceRule>("/compliance/rules", {
    method: "POST",
    token,
    body: input,
  });
}

export function updateComplianceRule(
  token: string,
  ruleId: string,
  input: Partial<ComplianceRuleInput>,
): Promise<ComplianceRule> {
  return request<ComplianceRule>(`/compliance/rules/${ruleId}`, {
    method: "PATCH",
    token,
    body: input,
  });
}

export function previewComplianceRuleImpact(
  token: string,
  input: { ruleId: string | null; proposed: ComplianceRuleInput },
): Promise<ComplianceRuleImpact> {
  return request<ComplianceRuleImpact>("/compliance/rules/impact", {
    method: "POST",
    token,
    body: { rule_id: input.ruleId, proposed: input.proposed },
  });
}

export function listComplianceMetrics(token: string): Promise<{ items: ComplianceMetric[] }> {
  return request<{ items: ComplianceMetric[] }>("/compliance/metrics", { token });
}

export function getComplianceMonitor(
  token: string,
  options: { page?: number; pageSize?: number } = {},
): Promise<ComplianceMonitorPage> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 100),
  });
  return request<ComplianceMonitorPage>(`/compliance/monitor?${params.toString()}`, {
    token,
  });
}

export function getInstitutionComplianceTrend(
  token: string,
  institutionId: string,
  limit = 50,
): Promise<ComplianceInstitutionTrend> {
  return request<ComplianceInstitutionTrend>(
    `/compliance/institutions/${institutionId}/trend?limit=${limit}`,
    { token },
  );
}

export function getComplianceConfig(token: string): Promise<ComplianceConfig> {
  return request<ComplianceConfig>("/compliance/config", { token });
}

export function updateComplianceConfig(
  token: string,
  input: ComplianceConfigUpdate,
): Promise<ComplianceConfig> {
  return request<ComplianceConfig>("/compliance/config", {
    method: "PUT",
    token,
    body: input,
  });
}

export function runComplianceMonitor(token: string): Promise<ComplianceMonitorRun> {
  return request<ComplianceMonitorRun>("/compliance/monitor/run", {
    method: "POST",
    token,
  });
}

export function addProgram(
  token: string,
  applicationId: string,
  input: ApplicationProgramInput,
): Promise<ApplicationProgram> {
  return request<ApplicationProgram>(`/applications/${applicationId}/programs`, {
    method: "POST",
    token,
    body: input,
  });
}

export function updateProgram(
  token: string,
  applicationId: string,
  programId: string,
  input: Partial<ApplicationProgramInput>,
): Promise<ApplicationProgram> {
  return request<ApplicationProgram>(
    `/applications/${applicationId}/programs/${programId}`,
    { method: "PATCH", token, body: input },
  );
}

export function deleteProgram(
  token: string,
  applicationId: string,
  programId: string,
): Promise<void> {
  return request<void>(`/applications/${applicationId}/programs/${programId}`, {
    method: "DELETE",
    token,
  });
}

export function submitApplication(
  token: string,
  applicationId: string,
): Promise<ApplicationSubmission> {
  return request<ApplicationSubmission>(`/applications/${applicationId}/submit`, {
    method: "POST",
    token,
  });
}

export function getAllowedActions(
  token: string,
  applicationId: string,
): Promise<AllowedActionsResponse> {
  return request<AllowedActionsResponse>(
    `/applications/${applicationId}/allowed-actions`,
    { token },
  );
}

export function getWorkflowDefinition(
  token: string,
  applicationType: string,
): Promise<WorkflowDefinition> {
  return request<WorkflowDefinition>(
    withQuery("/workflow/definition", { type: applicationType }),
    { token },
  );
}

export function getWorkflowTimeline(
  token: string,
  applicationId: string,
): Promise<WorkflowTimeline> {
  return request<WorkflowTimeline>(`/applications/${applicationId}/timeline`, {
    token,
  });
}

export function performWorkflowAction(
  token: string,
  applicationId: string,
  action: WorkflowAction,
  payload: WorkflowActionPayload = {},
): Promise<WorkflowActionResult> {
  return request<WorkflowActionResult>(
    `/applications/${applicationId}/actions/${action}`,
    { method: "POST", token, body: payload },
  );
}

export function listDeficiencies(
  token: string,
  applicationId: string,
): Promise<DeficiencyRecord[]> {
  return request<DeficiencyRecord[]>(
    `/applications/${applicationId}/deficiencies`,
    { token },
  );
}

export function listInspections(
  token: string,
  applicationId: string,
): Promise<InspectionRecord[]> {
  return request<InspectionRecord[]>(
    `/applications/${applicationId}/inspections`,
    { token },
  );
}

export function listCommitteeMembers(
  token: string,
  applicationId: string,
): Promise<CommitteeMember[]> {
  return request<CommitteeMember[]>(
    `/applications/${applicationId}/committee-members`,
    { token },
  );
}

export function uploadApplicationDocument(
  token: string,
  applicationId: string,
  docType: string,
  file: File,
  onProgress?: (percent: number) => void,
  signedWithDsc = true,
): Promise<DocumentRecord> {
  return new Promise<DocumentRecord>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/applications/${applicationId}/documents`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onerror = () => {
      reject(new ApiError(0, "The API is unreachable. Check that the backend is running."));
    };
    xhr.onload = () => {
      let payload: unknown = null;
      if (xhr.responseText) {
        try {
          payload = JSON.parse(xhr.responseText);
        } catch {
          payload = null;
        }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as DocumentRecord);
        return;
      }
      reject(buildApiError(xhr.status, payload));
    };

    const formData = new FormData();
    formData.append("doc_type", docType);
    formData.append("file", file);
    formData.append("signed_with_dsc", String(signedWithDsc));
    xhr.send(formData);
  });
}

export async function downloadApplicationDocument(
  token: string,
  document: DocumentRecord | ChecklistDocument,
): Promise<void> {
  const url = document.download_url;
  if (!url) {
    throw new ApiError(404, "Document is not available");
  }
  const response = await fetch(`${API_BASE_URL}${url}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const text = await response.text();
    let payload: unknown = null;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
    throw buildApiError(response.status, payload);
  }
  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = objectUrl;
  link.download = document.filename ?? "document";
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 0);
}

export function search(
  token: string,
  query: string,
): Promise<SearchResponse> {
  return request<SearchResponse>(
    withQuery("/search", { q: query }),
    { token },
  );
}

export function getAlerts(
  token: string,
  query: AlertQuery = {},
): Promise<Page<AlertRecord>> {
  return request<Page<AlertRecord>>(
    withQuery("/alerts", {
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
      unread: query.unread ? "true" : undefined,
      status: query.status,
      severity: query.severity,
      type: query.type,
      application_id: query.applicationId,
    }),
    { token },
  );
}

export function getAlertSummary(token: string): Promise<AlertSummary> {
  return request<AlertSummary>("/alerts/summary", { token });
}

export function acknowledgeAlert(
  token: string,
  alertId: string,
): Promise<AlertRecord> {
  return request<AlertRecord>(`/alerts/${alertId}/ack`, {
    method: "POST",
    token,
  });
}

export function listAlertRules(
  token: string,
  options: {
    includeInactive?: boolean;
    triggerType?: AlertTrigger;
    page?: number;
    pageSize?: number;
  } = {},
): Promise<AlertRulePage> {
  return request<AlertRulePage>(
    withQuery("/alert-rules", {
      include_inactive: String(options.includeInactive ?? true),
      trigger_type: options.triggerType,
      page: options.page ?? 1,
      page_size: options.pageSize ?? 100,
    }),
    { token },
  );
}

export function createAlertRule(
  token: string,
  input: AlertRuleInput,
): Promise<AlertRule> {
  return request<AlertRule>("/alert-rules", {
    method: "POST",
    token,
    body: input,
  });
}

export function updateAlertRule(
  token: string,
  ruleId: string,
  input: Partial<AlertRuleInput>,
): Promise<AlertRule> {
  return request<AlertRule>(`/alert-rules/${ruleId}`, {
    method: "PATCH",
    token,
    body: input,
  });
}

export function deleteAlertRule(token: string, ruleId: string): Promise<void> {
  return request<void>(`/alert-rules/${ruleId}`, {
    method: "DELETE",
    token,
  });
}

export function getTimeSimulation(
  token: string,
  days?: number,
): Promise<TimeSimulation> {
  return request<TimeSimulation>(
    withQuery("/dev/simulate-time", { days }),
    { token },
  );
}

export function updateTimeSimulation(
  token: string,
  update: TimeSimulationUpdate,
): Promise<TimeSimulation> {
  return request<TimeSimulation>("/dev/simulate-time", {
    method: "POST",
    token,
    body: update,
  });
}

export function getAuditLogs(
  token: string,
  query: AuditLogQuery,
): Promise<Page<AuditLogRecord>> {
  return request<Page<AuditLogRecord>>(
    withQuery("/audit-logs", {
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
      entity_type: query.entityType,
      entity_id: query.entityId,
      actor_id: query.actorId,
      start_date: query.startDate,
      end_date: query.endDate,
    }),
    { token },
  );
}

export type CommitteeType =
  | "SCRUTINY"
  | "RE_SCRUTINY"
  | "EVC"
  | "SHC"
  | "SAC"
  | "SCSC"
  | "EC"
  | "COUNCIL";

export interface SeatSelectionOut {
  expert_id: string;
  expert_name: string;
  seat_label: string;
  seat_role: string;
  reasons: string[];
}

export interface CommitteeSelectionOut {
  committee_id: string;
  committee_type: string;
  selection_seed: string;
  seats: SeatSelectionOut[];
  co_opted?: SeatSelectionOut | null;
  quorum_required: number;
  quorum_description: string;
  quorum_met: boolean;
  warnings: string[];
  status: string;
  mode: string;
  scheduled_at?: string | null;
  selected_at?: string | null;
}

export interface CommitteeSelectRequest {
  application_id?: string;
  complaint_id?: string;
  committee_type: string;
  include_co_opt?: boolean;
  selection_seed?: string;
  mode?: "ONLINE" | "HYBRID" | "PHYSICAL";
  scheduled_at?: string;
}

export interface QuorumCheckOut {
  committee_type: string;
  present_count: number;
  quorum_required: number;
  quorum_description: string;
  quorum_met: boolean;
  apH_clause: string;
}

export interface ExpertPoolOut {
  id: string;
  name: string;
  designation: string;
  institution_name?: string | null;
  state: string;
  aicte_region: string;
  email?: string | null;
  seat_tags: string[];
  years_experience: number;
  is_retired_hc_judge: boolean;
  recent_assignment_count: number;
  is_active: boolean;
  is_fictional: boolean;
}

export function getCommitteesForApplication(
  token: string,
  applicationId: string,
): Promise<CommitteeSelectionOut[]> {
  return request<CommitteeSelectionOut[]>(`/committees/application/${applicationId}`, { token });
}

export function selectCommittee(
  token: string,
  payload: CommitteeSelectRequest,
): Promise<CommitteeSelectionOut> {
  return request<CommitteeSelectionOut>("/committees/select", {
    method: "POST",
    token,
    body: payload,
  });
}

export function checkQuorum(
  token: string,
  committeeType: string,
  presentCount: number,
): Promise<QuorumCheckOut> {
  return request<QuorumCheckOut>(
    withQuery(`/committees/quorum/${committeeType}`, { present_count: presentCount }),
    { token },
  );
}

export function listExpertPool(
  token: string,
  activeOnly: boolean = true,
): Promise<ExpertPoolOut[]> {
  return request<ExpertPoolOut[]>(
    withQuery("/expert-pool", { active_only: activeOnly ? 1 : 0 }),
    { token },
  );
}
