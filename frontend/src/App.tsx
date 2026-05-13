import { Route, Router } from "@/lib/router";
import { AnnotationsPage } from "@/pages/AnnotationsPage";
import { CompanyPage } from "@/pages/CompanyPage";
import { DiscoverPage } from "@/pages/DiscoverPage";
import { HelloPage } from "@/pages/HelloPage";
import { NetworkPage } from "@/pages/NetworkPage";
import { PersonPage } from "@/pages/PersonPage";

// URL hierarchy (design.md §前端架构):
//   #/                          → landing
//   #/discover                  → DiscoverPage
//   #/p/<name>                  → PersonPage (hub if multi-bucket, else entity)
//   #/p/<name>/<bucket>         → PersonPage (entity for that bucket)
//   #/c/<stock_code>            → CompanyPage
//   #/n/<name>                  → NetworkPage (ego)
//   #/annotations               → AnnotationsPage (PR 10)
export function App() {
  return (
    <Router defaultPath="/">
      <Route path="/" component={HelloPage} />
      <Route path="/discover" component={DiscoverPage} />
      <Route path="/annotations" component={AnnotationsPage} />
      <Route path="/p/:name" component={PersonPage} />
      <Route path="/p/:name/:bucket" component={PersonPage} />
      <Route path="/c/:code" component={CompanyPage} />
      <Route path="/n/:name" component={NetworkPage} />
    </Router>
  );
}
