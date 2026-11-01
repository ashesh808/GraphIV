import Link from "next/link";
import { Icon } from "@/components/icon";

export default function NotFound() {
  return <main id="main-content" className="page-status"><Icon name="document" width="32" height="32" /><h1>Report not found</h1><p>This report may have moved, or the link may be incomplete.</p><Link className="button-secondary" href="/">Back to the library <Icon name="arrow" width="16" height="16" /></Link></main>;
}
