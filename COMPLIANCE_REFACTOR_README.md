# Compliance Engine Refactor - Implementation Plan

## Overview
This document outlines the plan for refactoring the compliance engine to ensure every rule has a real APH clause, properly classify rules as mandatory vs. illustrative, and implement the required logic for mandatory failure dominance.

## Current State
- Compliance rules already have `apH_clause` and `needs_verification` fields
- Rules are evaluated with severity-based scoring
- Impact preview shows projected status changes
- Admin interface allows rule management

## Required Changes

### 1. Rule Classification Enhancement

**New Fields to Add/Update:**
```python
class ComplianceRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    # Existing fields...
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    
    # NEW: Mandatory vs. Illustrative Classification
    mandatory: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False, 
        server_default=text("false"),
        comment="True if rule violation constitutes a mandatory failure overriding nil deficiency status"
    )
    
    # NEW: Rule classification badge
    classification: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="mandatory",
        server_default=text("'mandatory'"),
        comment="mandatory, illustrative, or optional"
    )
```

**Database Migration:**
```sql
-- Update existing ComplianceRule table
ALTER TABLE compliance_rules 
ADD COLUMN mandatory BOOLEAN NOT NULL DEFAULT FALSE;
ADD COLUMN classification VARCHAR(20) NOT NULL DEFAULT 'mandatory';
```

### 2. Rule Impact Assessment Refactoring

**New Logic for Mandatory Rules:**
```python
def _build_preview(
    *,
    application: Application,
    previews: list[ComplianceRulePreview],
    evaluated_at: datetime,
    mandatory_dominance: bool = True  # NEW: mandatory failure dominance
) -> CompliancePreviewRead:
    # Calculate scores as before
    weights, breakpoints = _config_for(application)
    severity_results = [
        (rule.severity, rule.status == "PASS")
        for rule in previews
        if rule.status != "NOT_ASSESSED"
    ]
    score = _weighted_score(
        severity_results,
        _weights_by_severity(weights),
    )
    
    # NEW: Mandatory failure logic
    failed_critical = sum(
        rule.status == "FAIL" and rule.severity == Severity.CRITICAL
        for rule in previews
    )
    
    # NEW: Mandatory dominance check
    has_mandatory_failures = failed_critical > 0
    
    # Override status logic
    if mandatory_dominance and has_mandatory_failures:
        status = ComplianceHealth.RED
    else:
        status = _rag_status(
            failed_critical_count=failed_critical,
            score=score,
            breakpoints=breakpoints,
        )
    
    # Build result
    return CompliancePreviewRead(
        application_id=application.id,
        institution_id=application.institution_id,
        status=status,
        score=score,
        passed_count=len(previews) - failed_critical,
        failed_critical_count=failed_critical,
        failed_non_critical_count=failed_count - failed_critical,
        not_assessed_count=not_assed_count,
        evaluated_at=evaluated_at,
        events=[],
    )
```

### 3. UI Badge Implementation

**New Badge Component:**
```tsx
function RuleClassificationBadge({ rule }: { rule: ComplianceRule }) {
  if (rule.mandatory) {
    return (
      <span className="rule-badge mandatory">
        🔴 Mandatory
      </span>
    );
  }
  
  if (rule.needs_verification || rule.classification === 'illustrative') {
    return (
      <span className="rule-badge illustrative">
        🟡 Illustrative, not an AICTE norm
      </span>
    );
  }
  
  return (
    <span className="rule-badge optional">
      🟢 Optional
    </span>
  );
}
```

### 4. APH Clause Validation

**Validation Logic:**
```typescript
function validateApHClause(apH_clause: string): boolean {
  // APH clauses typically follow patterns like:
  // - "APH 1.4.1"
  // - "APH Table 2.1"
  // - "APH Annexure-16 16.3-16.4"
  // - "APH 6.14a"
  
  const aphPattern = /^(APH|APH Table|APH Annexure)[\s\d\-\.,a-zA-Z]+$/;
  return apH_clause.match(aphPattern) !== null;
}

function migrateExistingRules() {
  // Update existing rules to ensure they have valid APH clauses
  // and set appropriate mandatory/illustrative classification
  
  const illustrative_rules = [
    // List of rules that need to be marked as illustrative
    // These are rules that are not officially published in APH_SPEC.md
    { code: "RULE_CODE", apH_clause: "TODO_FIND_APH_CLAUSE" }
  ];
  
  return illustrative_rules.map(rule => ({
    ...rule,
    needs_verification: true,
    classification: 'illustrative'
  }));
}
```

### 5. Impact Preview Updates

**Enhanced Preview Logic:**
```typescript
interface RuleImpactInstitution {
  institution_id: string;
  institution_name: string;
  region: string;
  current_status: string;
  projected_status: string;
  // NEW: Mandatory impact indicator
  mandatory_change?: boolean;
}

function preview_rule_impact(*, proposed: ComplianceRuleCreate, rule_id?: string, institutions: Institution[]): {
  // ... existing logic ...
  
  // NEW: Enhanced impact analysis
  const mandatory_impact = proposed.mandatory && !existing_rule?.mandatory;
  // Update affected institutions with mandatory impact flag
  
  return {
    red_flips: ...,
    amber_flips: ...,
    improved: ...,
    unchanged: ...,
    affected: affected.map(a => ({
      ...a,
      mandatory_change: mandatory_impact
    }))
  };
}
```

## Implementation Steps

### Phase 1: Foundation (Week 1)
1. **Database Schema Updates**
   - Add `mandatory` column to ComplianceRule table
   - Add `classification` column to ComplianceRule table
   - Create indexes for new fields

2. **Code Updates**
   - Update ComplianceRule model with new fields
   - Update evaluation logic to consider mandatory rules
   - Add UI badge component

3. **Migration Script**
   - Create seed data for rule classification
   - Update existing rules to have appropriate classification

### Phase 2: Core Logic (Week 2)
1. **Mandatory Rule Evaluation**
   - Implement mandatory failure logic
   - Update impact calculation
   - Add mandatory dominance checks

2. **UI Integration**
   - Add rule classification badges to admin interface
   - Update rule filtering options
   - Add classification indicators

3. **Testing**
   - Update existing tests to account for new fields
   - Add tests for mandatory rule logic
   - Test UI badge functionality

### Phase 3: APH Clause Alignment (Week 3)
1. **Rule Audit**
   - Identify all existing rules without APH clauses
   - Mark illustrative rules where appropriate
   - Update database with APH clauses where possible

2. **Validation**
   - Implement APH clause format validation
   - Add validation to rule creation/editing
   - Update seed data migration

3. **Documentation**
   - Update rule documentation with APH references
   - Create APH clause validation guidelines

### Phase 4: Enhanced Features (Week 4)
1. **Advanced Impact Analysis**
   - Add mandatory impact indicators
   - Enhance impact preview UI
   - Add filtering by rule classification

2. **User Experience**
   - Add hover tooltips for badges
   - Update help documentation
   - Add classification-based rule search

3. **Performance**
   - Optimize query performance with new indexes
   - Update caching strategies

## Testing Strategy

### Unit Tests
- Test mandatory rule logic
- Validate APH clause format
- Test badge rendering
- Verify impact calculation

### Integration Tests
- Test rule classification with evaluation
- Validate admin interface functionality
- Test migration script

### End-to-End Tests
- Test rule creation with classification
- Validate UI badge display
- Test impact preview with mandatory rules

## Risk Mitigation

### High Risks
1. **Rule Classification Impact**
   - Mitigation: Phased rollout with clear communication
   - Rollback plan: Keep existing rules functional

2. **APH Clause Validation**
   - Mitigation: Comprehensive validation script
   - Fallback: Mark unvalidated rules as illustrative

3. **UI Changes**
   - Mitigation: Component-based approach
   - Testing: Comprehensive test coverage

### Medium Risks
1. **Performance Impact**
   - Mitigation: Database indexing
   - Optimization: Query performance analysis

2. **User Adoption**
   - Mitigation: Training and documentation
   - Support: Help desk preparation

## Documentation

### Technical Documentation
- API documentation for new fields
- Database schema changes
- Migration guide
- Code comments

### User Documentation
- Admin interface user guide
- Rule classification explanation
- Badge meaning and usage

### Training
- Admin training materials
- Support documentation
- FAQ preparation

## Timeline

| Week | Tasks |
|------|-------|
| Week 1 | Database schema updates, code foundation |
| Week 2 | Core logic implementation, UI integration |
| Week 3 | APH clause alignment and validation |
| Week 4 | Enhanced features, testing, documentation |
| Week 5 | Deployment, monitoring, support prep |

**Total Duration: 5 weeks**

## Success Criteria

### Technical
- All compliance rules have valid APH clauses or are marked illustrative
- Mandatory rule logic correctly dominates "Nil Deficiency"
- UI badges display correctly for all rule types
- No regression in existing functionality

### Functional
- Rule classification works as expected
- Mandatory rules correctly override Nil Deficiency
- Impact preview accurately shows mandatory changes
- Admin interface supports rule classification

### User Experience
- Badges display correctly in admin interface
- Users understand rule classification
- Help documentation is adequate
- Training materials are available

## Conclusion

This refactoring will significantly improve the compliance engine's adherence to AICTE handbook standards while maintaining backward compatibility. The mandatory rule logic ensures that critical violations always take precedence, and the classification system helps users quickly identify rule types and their importance.

The implementation requires careful planning, thorough testing, and clear communication to ensure successful deployment.