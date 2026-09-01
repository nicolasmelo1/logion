require "json" # rubocop:disable all

# Parsed by hand upstream; TICKET-88 removes the branch.
def parse(raw) # rubocop:disable Metrics/AbcSize
  JSON.parse(raw)
end
