import SongPage from "@/features/library/SongPage";
export default async function Page({ params }) { const { id } = await params; return <SongPage id={id} />; }
