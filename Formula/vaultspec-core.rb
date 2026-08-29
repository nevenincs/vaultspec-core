class VaultspecCore < Formula
  desc "Spec-driven development framework - vaultspec-core CLI and MCP server"
  homepage "https://github.com/nevenincs/vaultspec-core"
  version "0.1.61"
  license "MIT"

  livecheck do
    url :stable
    regex(/^vaultspec-core-v(\d+(?:\.\d+)+)$/i)
    strategy :github_latest
  end

  on_macos do
    on_arm do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-core-aarch64-apple-darwin"
      sha256 "688776739140aeaf69056823dd7821d46c9b6ade1483245f8b7b0b68603a4800"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-mcp-aarch64-apple-darwin"
        sha256 "667882b91d8dadb9e88da9bcc8cbb5c5773b1177880c4dd61f1a97ce315c78fb"
      end
    end

    on_intel do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-core-x86_64-apple-darwin"
      sha256 "16f3d043a6b9469fd3425812eb6e2485176a6d24f07a8a9d08fe3849d2ac292b"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-mcp-x86_64-apple-darwin"
        sha256 "4005d03b6329a38b0fc830b0b3a57fe0b27029f7c5493610d48e32e691d3e155"
      end
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-core-x86_64-unknown-linux-gnu"
      sha256 "88a9fdd13ea7f03ef64fd5959215a049c0f15f85e72843d84d5a2f4c79cc4336"

      resource "vaultspec-mcp" do
        url "https://github.com/nevenincs/vaultspec-core/releases/download/vaultspec-core-v0.1.61/vaultspec-mcp-x86_64-unknown-linux-gnu"
        sha256 "20dd0b7c311328adb67ab07fb3e665e88deffcf4c28a2c2b4a46109d7e95eb01"
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

  def caveats
    <<~EOS
      Installs vaultspec-core and vaultspec-mcp.
      First launch bootstraps the pinned runtime; needs network once.
      Verify with: vaultspec-core --version
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/vaultspec-core --version")
  end
end
