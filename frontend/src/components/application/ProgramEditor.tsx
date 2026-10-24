import { useState } from "react";
import { Pencil, Plus, Save, Trash2, X } from "lucide-react";

import { Button, Input, Select, useToast } from "@/components/ui";
import {
  PROGRAM_LEVEL_OPTIONS,
  createEmptyProgram,
  programLevelLabel,
  toIntegerOrNull,
} from "@/lib/application";
import {
  ApiError,
  addProgram,
  deleteProgram,
  updateProgram,
  type ApplicationProgram,
  type ApplicationProgramInput,
} from "@/lib/api";

interface ProgramEditorProps {
  applicationId: string;
  token: string;
  programs: ApplicationProgram[];
  disabled?: boolean;
  onChanged: () => void;
}

interface ProgramFormState {
  program_name: string;
  level: string;
  intake: string;
  faculty_count: string;
  lab_count: string;
}

function formFromProgram(program?: ApplicationProgram): ProgramFormState {
  const defaults = createEmptyProgram();
  return {
    program_name: program?.program_name ?? defaults.program_name,
    level: program?.level ?? defaults.level,
    intake: String(program?.intake ?? defaults.intake),
    faculty_count: String(program?.faculty_count ?? defaults.faculty_count),
    lab_count: String(program?.lab_count ?? defaults.lab_count),
  };
}

function payloadFromForm(form: ProgramFormState): ApplicationProgramInput {
  return {
    program_name: form.program_name.trim(),
    level: form.level,
    intake: toIntegerOrNull(form.intake) ?? 0,
    faculty_count: toIntegerOrNull(form.faculty_count) ?? 0,
    lab_count: toIntegerOrNull(form.lab_count) ?? 0,
  };
}

function validateForm(form: ProgramFormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!form.program_name.trim()) {
    errors.program_name = "Programme name is required.";
  }
  const values: Array<[string, string, string]> = [
    ["intake", form.intake, "Intake"],
    ["faculty_count", form.faculty_count, "Faculty count"],
    ["lab_count", form.lab_count, "Laboratory count"],
  ];
  for (const [key, raw, label] of values) {
    const value = toIntegerOrNull(raw);
    if (value === null || value < 0) {
      errors[key] = `${label} must be a whole number of 0 or more.`;
    }
  }
  return errors;
}

export default function ProgramEditor({
  applicationId,
  token,
  programs,
  disabled,
  onChanged,
}: ProgramEditorProps) {
  const { toast } = useToast();
  const [formOpen, setFormOpen] = useState(programs.length === 0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ProgramFormState>(() => formFromProgram());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

  const resetForm = () => {
    setForm(formFromProgram());
    setEditingId(null);
    setErrors({});
    setRequestError(null);
    setFormOpen(programs.length === 0);
  };

  const openAdd = () => {
    setForm(formFromProgram());
    setEditingId(null);
    setErrors({});
    setRequestError(null);
    setFormOpen(true);
  };

  const openEdit = (program: ApplicationProgram) => {
    setForm(formFromProgram(program));
    setEditingId(program.id);
    setErrors({});
    setRequestError(null);
    setFormOpen(true);
  };

  const handleSave = async () => {
    const nextErrors = validateForm(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setSaving(true);
    setRequestError(null);
    try {
      const payload = payloadFromForm(form);
      if (editingId) {
        await updateProgram(token, applicationId, editingId, payload);
        toast({ title: "Programme updated", variant: "success" });
      } else {
        await addProgram(token, applicationId, payload);
        toast({ title: "Programme added", variant: "success" });
      }
      onChanged();
      setForm(formFromProgram());
      setEditingId(null);
      setFormOpen(false);
    } catch (saveError) {
      setRequestError(
        saveError instanceof ApiError
          ? saveError.message
          : "The programme could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (program: ApplicationProgram) => {
    if (!window.confirm(`Remove ${program.program_name} from this application?`)) {
      return;
    }
    setDeletingId(program.id);
    setRequestError(null);
    try {
      await deleteProgram(token, applicationId, program.id);
      toast({ title: "Programme removed", variant: "success" });
      onChanged();
      if (editingId === program.id) {
        resetForm();
      }
    } catch (deleteError) {
      setRequestError(
        deleteError instanceof ApiError
          ? deleteError.message
          : "The programme could not be removed.",
      );
    } finally {
      setDeletingId(null);
    }
  };

  const updateForm = (patch: Partial<ProgramFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
    setErrors({});
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-13 text-ink-500">
          {programs.length === 0
            ? "No programmes added yet."
            : `${programs.length} programme${programs.length === 1 ? "" : "s"} on this application.`}
        </p>
        {!disabled ? (
          <Button variant="secondary" size="sm" onClick={openAdd}>
            <Plus aria-hidden="true" className="size-4" />
            Add programme
          </Button>
        ) : null}
      </div>

      {requestError ? (
        <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong" role="alert">
          {requestError}
        </p>
      ) : null}

      {formOpen ? (
        <section className="rounded-input border border-line bg-paper p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-14 font-semibold text-ink">
              {editingId ? "Edit programme" : "New programme"}
            </h3>
            {programs.length > 0 ? (
              <Button variant="quiet" size="sm" onClick={resetForm} aria-label="Close programme form">
                <X aria-hidden="true" className="size-4" />
              </Button>
            ) : null}
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              label="Programme name"
              required
              value={form.program_name}
              error={errors.program_name}
              placeholder="e.g. B.Tech Computer Science"
              onChange={(event) => updateForm({ program_name: event.target.value })}
              containerClassName="sm:col-span-2"
            />
            <Select
              label="Level"
              options={PROGRAM_LEVEL_OPTIONS}
              value={form.level}
              onValueChange={(value) => updateForm({ level: value })}
              required
            />
            <Input
              label="Sanctioned intake"
              type="number"
              min={0}
              step={1}
              required
              value={form.intake}
              error={errors.intake}
              onChange={(event) => updateForm({ intake: event.target.value })}
            />
            <Input
              label="Faculty count"
              type="number"
              min={0}
              step={1}
              required
              value={form.faculty_count}
              error={errors.faculty_count}
              onChange={(event) => updateForm({ faculty_count: event.target.value })}
            />
            <Input
              label="Laboratory count"
              type="number"
              min={0}
              step={1}
              required
              value={form.lab_count}
              error={errors.lab_count}
              onChange={(event) => updateForm({ lab_count: event.target.value })}
            />
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="quiet" size="sm" onClick={resetForm} disabled={saving}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
              <Save aria-hidden="true" className="size-4" />
              {saving ? "Saving…" : editingId ? "Save changes" : "Add programme"}
            </Button>
          </div>
        </section>
      ) : null}

      {programs.length > 0 ? (
        <ul className="divide-y divide-line rounded-input border border-line">
          {programs.map((program) => (
            <li key={program.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-14 font-medium text-ink">{program.program_name}</p>
                <p className="mt-1 text-12 text-ink-500">
                  {programLevelLabel(program.level)} · intake {program.intake} ·{" "}
                  {program.faculty_count} faculty · {program.lab_count} labs
                </p>
              </div>
              {!disabled ? (
                <div className="flex shrink-0 gap-2">
                  <Button variant="quiet" size="sm" onClick={() => openEdit(program)}>
                    <Pencil aria-hidden="true" className="size-4" />
                    Edit
                  </Button>
                  <Button
                    variant="quiet"
                    size="sm"
                    className="text-breach-strong hover:bg-breach-soft"
                    onClick={() => void handleDelete(program)}
                    disabled={deletingId === program.id}
                  >
                    <Trash2 aria-hidden="true" className="size-4" />
                    {deletingId === program.id ? "Removing…" : "Remove"}
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
