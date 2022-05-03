
import interpret

prgs = [
	"fibonacci",
	"helloworld",
	"turing",
	"lfsr"
	]

iprgs = [
	"echo",
	"str_inv"
	]

for p in prgs:
	print(f'\n\nRunning {p}')
	interpret.main([f"--source=test/{p}.xml"])

for p in iprgs:
	print(f'\n\nRunning {p}')
	interpret.main([f"--source=test/{p}.xml", f"--input=input.txt"])

