import UploadPage from "@/features/library/UploadPage";
export default async function Page({ params }) { const { id } = await params; return <UploadPage id={id} />; }
