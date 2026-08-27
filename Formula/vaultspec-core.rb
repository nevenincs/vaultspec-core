class VaultspecCore < Formula
  desc "Spec-driven development framework - vaultspec-core CLI and MCP server"
  homepage "https://github.com/nevenincs/vaultspec-core"
  version "0.1.60"
  license "MIT"

  livecheck do
    url :stable
    regex(/^vaultspec-core-v(\d+(?:\.\d+)+)$/i)
    strategy :github_latest
  end

  on_macos do
    on_arm do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-core-aarch64-apple-darwin"
      sha256 "b961933dccbc56c8f7ca36856a5760007c27de4a890bdf98004d65e483461e00"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-mcp-aarch64-apple-darwin"
        sha256 "cdf7baf97d1c5e1ea09eb05de1372882c0c0cb3548225ed7d37b58767db6647f"
      end
    end

    on_intel do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-core-x86_64-apple-darwin"
      sha256 "76ffd4d488d531d2562489ce7a0984d92d54bf472e8a36b5cf269f9eddadaccc"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-mcp-x86_64-apple-darwin"
        sha256 "be20e0316584b65992e15c02f34cb3dfca66b431c5c9d9f8d84e7ff9f1e5d9b3"
      end
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-core-x86_64-unknown-linux-gnu"
      sha256 "fdcc640b222eae4bae75b600fc71079df3a9e9e4d0ad03337131b71341e4a20a"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.60/vaultspec-mcp-x86_64-unknown-linux-gnu"
        sha256 "b574e8121f22a3f6bb183dd11112400ddf2c32c0acddf911525d9f820c804857"
      end
    end
  end

  def install
    vendor = OS.mac? ? "apple-darwin" : "unknown-linux-gnu"
    arch = Hardware::CPU.arm? ? "aarch64" : "x86_64"
    triple = "#{arch}-#{vendor}"

    bin.install "vaultspec-core-#{triple}" => "vaultspec-core"

    resource("vaultspec-mcp").stage do
      bin.install "vaultspec-mcp-#{triple}" => "vaultspec-mcp"
    end
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/vaultspec-core --version")
  end
end
