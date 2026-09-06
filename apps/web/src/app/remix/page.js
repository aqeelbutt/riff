import { Suspense } from "react";
import RemixPage from "@/features/remix/RemixPage";
export default function Page() { return <Suspense fallback={null}><RemixPage /></Suspense>; }
