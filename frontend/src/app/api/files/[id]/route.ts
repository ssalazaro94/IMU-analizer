import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { FileRow } from "@/lib/types";

export async function DELETE(_request: Request, ctx: RouteContext<"/api/files/[id]">) {
  const { id } = await ctx.params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "No autenticado." }, { status: 401 });
  }

  const { data: fileRow, error: fileError } = await supabase
    .from("files")
    .select("*")
    .eq("id", id)
    .single<FileRow>();

  if (fileError || !fileRow) {
    return NextResponse.json({ error: "Archivo no encontrado." }, { status: 404 });
  }

  const { error: storageError } = await supabase.storage
    .from("csv-uploads")
    .remove([fileRow.storage_path]);

  if (storageError) {
    return NextResponse.json({ error: "No se pudo borrar el CSV del storage." }, { status: 500 });
  }

  const { error: deleteError } = await supabase.from("files").delete().eq("id", id);

  if (deleteError) {
    return NextResponse.json({ error: "No se pudo borrar el registro." }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
