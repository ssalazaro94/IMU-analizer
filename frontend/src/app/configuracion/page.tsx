import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getCurrentUser } from "@/lib/supabase/profile";
import type { EquationSettings } from "@/lib/types";
import { SettingsForm } from "./settings-form";

export default async function ConfiguracionPage() {
  const user = await getCurrentUser();
  if (!user || user.role !== "root") {
    redirect("/");
  }

  const supabase = await createClient();
  const { data: settings } = await supabase
    .from("equation_settings")
    .select("*")
    .eq("id", 1)
    .single<EquationSettings>();

  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-10">
      <div>
        <Link href="/" className="text-sm text-neutral-600 hover:text-neutral-900">
          ← Volver
        </Link>
        <h1 className="mt-2 text-lg font-semibold text-neutral-900">Configuración del algoritmo</h1>
        <p className="text-sm text-neutral-600">
          Ajustá los valores constantes que usa el análisis de marcha. Las ecuaciones en sí no son
          editables, solo estos parámetros. Esta pantalla es exclusiva para usuarios root.
        </p>
      </div>

      {settings ? (
        <SettingsForm initialSettings={settings} />
      ) : (
        <p className="text-sm text-red-600">No se pudieron cargar los parámetros.</p>
      )}
    </main>
  );
}
