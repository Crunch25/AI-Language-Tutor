// lib/validations/auth.ts

import * as z from "zod";

// Matches backend: at least 1 uppercase, 1 lowercase, 1 digit, 1 special character
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_\-#^~`+=])[A-Za-z\d@$!%*?&_\-#^~`+=]{8,128}$/;

export const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  full_name: z.string()
    .min(1, "Full name is required.")
    .max(150, "Full name cannot exceed 150 characters."),
  email: z.string().email("Please enter a valid email address."),
  native_language: z.string()
    .min(2, "Please select a native language.")
    .max(50),
  target_language: z.string()
    .min(2, "Please select a target language.")
    .max(50),
  password: z.string()
    .min(8, "Password must be at least 8 characters.")
    .max(128, "Password cannot exceed 128 characters.")
    .regex(
      PASSWORD_REGEX,
      "Password must contain at least one uppercase, lowercase, number, and special character."
    ),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

export type RegisterFormData = z.infer<typeof registerSchema>;