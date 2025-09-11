// codegen.ts
import { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  // URL of your running Apollo Gateway
  schema: "http://localhost:4000/graphql",

  // Where to look for .ts and .tsx files containing GraphQL queries
  documents: ["src/**/*.ts", "src/**/*.tsx"],

  // Where to output the generated types
  generates: {
    "./src/gql/": {
      preset: "client",
      plugins: [],
      presetConfig: {
        gqlTagName: "gql",
      },
    },
  },
  ignoreNoDocuments: true,
};

export default config;
