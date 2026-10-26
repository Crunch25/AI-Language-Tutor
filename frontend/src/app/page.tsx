import { redirect } from "next/navigation";

export default function RootPage() {
  // Automatically route root visitors to the login screen
  redirect("/login");
}