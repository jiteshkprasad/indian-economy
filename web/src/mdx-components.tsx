import type { MDXComponents } from "mdx/types";

// Required by @next/mdx with the App Router. Typography only (PLAN §3.9):
// <StoryFig> and <DataFig> are passed per page through the MDX `components` prop,
// never registered here.
const components: MDXComponents = {
  table: (props) => (
    <div style={{ overflowX: "auto" }}>
      <table {...props} />
    </div>
  ),
};

export function useMDXComponents(): MDXComponents {
  return components;
}
