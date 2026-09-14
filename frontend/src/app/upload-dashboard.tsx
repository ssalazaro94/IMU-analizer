"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { logout } from "./actions";
import type { AnalysisResultRow, FileRow, FileStatus, Pierna } from "@/lib/types";

const ESTADO_LABEL: Record<FileStatus, string> = {
  pending: "En cola",
  processing: "Procesando",
  done: "Listo",
  error: "Error",
};

const ESTADO_CLASS: Record<FileStatus, string> = {
  pending: "text-neutral-600",
  processing: "text-[#1A73E8]",
  done: "text-green-700",
  error: "text-red-600",
};

export function UploadDashboard({
  user,
  initialFiles,
  initialResults,
}: {
  user: { id: string; email: string; role: "root" | "admin" };
  initialFiles: FileRow[];
  initialResults: Record<string, AnalysisResultRow>;
}) {
  const [files, setFiles] = useState<FileRow[]>(initialFiles);
  const [results, setResults] = useState<Record<string, AnalysisResultRow>>(initialResults);
  const [pierna, setPierna] = useState<Pierna>("derecha");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reanalyzingId, setReanalyzingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const supabase = useMemo(() => createClient(), []);

  useEffect(() => {
    const channel = supabase
      .channel("files-y-resultados")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "files" },
        (payload) => {
          if (payload.eventType === "DELETE") {
            setFiles((prev) => prev.filter((f) => f.id !== (payload.old as FileRow).id));
            return;
          }
          const row = payload.new as FileRow;
          setFiles((prev) => {
            const sinEsta = prev.filter((f) => f.id !== row.id);
            return [row, ...sinEsta].sort(
              (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
            );
          });
        },
      )
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "analysis_results" },
        (payload) => {
          const row = payload.new as AnalysisResultRow;
          setResults((prev) => ({ ...prev, [row.file_id]: row }));
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [supabase]);

  async function handleSubmit(formEvent: React.FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    setError(null);

    const form = formEvent.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement;
    const file = fileInput.files?.[0];
    if (!file) {
      setError("Seleccioná un archivo CSV.");
      return;
    }

    const formData = new FormData();
    formData.set("file", file);
    formData.set("pierna", pierna);

    setUploading(true);
    try {
      const response = await fetch("/api/analyze", { method: "POST", body: formData });
      const body = await response.json();
      if (!response.ok) {
        setError(body.error ?? "No se pudo subir el archivo.");
      } else {
        form.reset();
      }
    } catch {
      setError("No se pudo conectar con el servidor.");
    } finally {
      setUploading(false);
    }
  }

  async function handleReanalyze(fileId: string) {
    setReanalyzingId(fileId);
    try {
      await fetch("/api/reanalyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId }),
      });
    } finally {
      setReanalyzingId(null);
    }
  }

  async function handleDownloadReport(fileId: string) {
    setDownloadingId(fileId);
    try {
      const response = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId }),
      });
      if (!response.ok) {
        setError("No se pudo generar el reporte.");
        return;
      }
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const nombre = disposition.match(/filename="(.+)"/)?.[1] ?? "reporte.pdf";
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = nombre;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(fileId: string) {
    if (!window.confirm("¿Borrar este archivo y sus resultados? Esta acción no se puede deshacer.")) {
      return;
    }
    setDeletingId(fileId);
    try {
      const response = await fetch(`/api/files/${fileId}`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(body?.error ?? "No se pudo borrar el archivo.");
        return;
      }
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      setResults((prev) => {
        const { [fileId]: _omit, ...resto } = prev;
        return resto;
      });
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">Análisis de Marcha IMU</h1>
          <p className="text-sm text-neutral-600">
            {user.email} · {user.role === "root" ? "Root" : "Admin"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {user.role === "root" && (
            <Link
              href="/configuracion"
              className="rounded-md border border-neutral-300 px-3.5 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50"
            >
              Configuración
            </Link>
          )}
          <form action={logout}>
            <button
              type="submit"
              className="rounded-md border border-neutral-300 px-3.5 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50"
            >
              Cerrar sesión
            </button>
          </form>
        </div>
      </header>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6"
      >
        <h2 className="text-sm font-semibold text-neutral-900">Subir CSV</h2>

        <input
          type="file"
          name="file"
          accept=".csv,text/csv"
          className="block w-full text-sm text-neutral-600 file:mr-4 file:rounded-lg file:border-0 file:bg-neutral-100 file:px-3.5 file:py-2 file:text-sm file:font-medium file:text-neutral-700 hover:file:bg-neutral-200"
        />

        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Pierna</label>
          <select
            value={pierna}
            onChange={(e) => setPierna(e.target.value as Pierna)}
            className="w-full rounded-md border border-neutral-300 px-3.5 py-2.5 text-sm text-neutral-900 outline-none focus:border-[#1A73E8] focus:ring-1 focus:ring-[#1A73E8]"
          >
            <option value="derecha">Derecha</option>
            <option value="izquierda">Izquierda</option>
          </select>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={uploading}
          className="w-full rounded-md bg-[#1A73E8] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#1558b0] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {uploading ? "Subiendo..." : "Analizar"}
        </button>
      </form>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-neutral-900">Archivos</h2>

        {files.length === 0 && (
          <p className="text-sm text-neutral-600">Todavía no subiste ningún archivo.</p>
        )}

        {files.map((file) => {
          const result = results[file.id];
          return (
            <div
              key={file.id}
              className="rounded-lg border border-neutral-200 bg-white p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-neutral-900">
                    {file.nombre_original}
                  </p>
                  <p className="text-xs text-neutral-600">
                    Pierna {file.pierna} · {new Date(file.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={`shrink-0 text-xs font-medium ${ESTADO_CLASS[file.status]}`}>
                  {ESTADO_LABEL[file.status]}
                </span>
              </div>

              {file.status === "error" && file.error_message && (
                <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3">
                  <p className="text-xs font-medium text-red-800">No se pudo completar el análisis</p>
                  <p className="mt-1 text-xs leading-relaxed text-red-700">{file.error_message}</p>
                </div>
              )}

              {file.status === "done" && result && (
                <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-neutral-100 pt-3 text-xs sm:grid-cols-4">
                  <div>
                    <dt className="text-neutral-600">Duración de ciclo</dt>
                    <dd className="font-medium text-neutral-900">
                      {result.duracion_ciclo_promedio_s?.toFixed(3) ?? "—"} s
                    </dd>
                  </div>
                  <div>
                    <dt className="text-neutral-600">Tiempo de apoyo</dt>
                    <dd className="font-medium text-neutral-900">
                      {result.tiempo_apoyo_promedio_s?.toFixed(3) ?? "—"} s
                    </dd>
                  </div>
                  <div>
                    <dt className="text-neutral-600">Tiempo de balanceo</dt>
                    <dd className="font-medium text-neutral-900">
                      {result.tiempo_balanceo_promedio_s?.toFixed(3) ?? "—"} s
                    </dd>
                  </div>
                  <div>
                    <dt className="text-neutral-600">Cadencia</dt>
                    <dd className="font-medium text-neutral-900">
                      {result.cadencia_promedio_pasos_min?.toFixed(1) ?? "—"} pasos/min
                    </dd>
                  </div>
                </dl>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {(file.status === "done" || file.status === "error") && (
                  <button
                    onClick={() => handleReanalyze(file.id)}
                    disabled={reanalyzingId === file.id}
                    className="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium text-neutral-700 transition hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {reanalyzingId === file.id ? "Enviando..." : "Volver a analizar"}
                  </button>
                )}
                {file.status === "done" && (
                  <button
                    onClick={() => handleDownloadReport(file.id)}
                    disabled={downloadingId === file.id}
                    className="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium text-neutral-700 transition hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {downloadingId === file.id ? "Generando..." : "Descargar reporte (PDF)"}
                  </button>
                )}
                <button
                  onClick={() => handleDelete(file.id)}
                  disabled={deletingId === file.id}
                  className="ml-auto rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {deletingId === file.id ? "Borrando..." : "Borrar"}
                </button>
              </div>
            </div>
          );
        })}
      </section>
    </main>
  );
}
