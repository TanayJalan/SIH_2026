import { Input, type InputProps } from "@/components/ui/Input";

export type DatePickerProps = Omit<InputProps, "type">;

/**
 * Native date input styled with the design system. It keeps the browser's
 * keyboard handling and screen-reader semantics.
 */
export function DatePicker(props: DatePickerProps) {
  return <Input type="date" {...props} />;
}
