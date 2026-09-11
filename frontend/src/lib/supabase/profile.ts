import { createClient } from "@/lib/supabase/server";

export type Role = "root" | "admin";

export type CurrentUser = {
  id: string;
  email: string;
  role: Role;
};

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  return {
    id: user.id,
    email: user.email ?? "",
    role: (profile?.role as Role) ?? "admin",
  };
}
