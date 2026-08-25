const { getDefaultConfig } = require("expo/metro-config");
const exclusionList = require("metro-config/private/defaults/exclusionList").default;
const { withNativeWind } = require("nativewind/metro");

const config = getDefaultConfig(__dirname);
config.resolver.blockList = exclusionList([
  /.*\/android\/\.gradle\/.*/,
  /.*\/android\/app\/build\/.*/,
  /.*\/android\/build\/.*/,
  /.*\/node_modules\/[^/]+\/android\/build\/.*/,
]);

module.exports = withNativeWind(config, {
  input: "./global.css",
  // Force write CSS to file system instead of virtual modules
  // This fixes iOS styling issues in development mode
  forceWriteFileSystem: true,
});
