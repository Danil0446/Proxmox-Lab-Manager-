const path = require("path");
const Dotenv = require("dotenv-webpack");

module.exports = {
  entry: "./src/index.jsx",
  plugins: [
    new Dotenv({ path: path.resolve(__dirname, ".env") })
  ],
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "bundle.js",
    publicPath: "/"
  },
  resolve: {
    extensions: [".js", ".jsx"]
  },
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader"
        }
      },
      {
        test: /\.css$/i,
        use: ["style-loader", "css-loader"]
      }
    ]
  },
  devServer: {
    host: "0.0.0.0",
    allowedHosts: "all",
    static: {
      directory: path.join(__dirname, "public")
    },
    historyApiFallback: true,
    port: 3000
  }
};

