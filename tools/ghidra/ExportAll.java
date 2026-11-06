import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
public class ExportAll extends GhidraScript {
  public void run() throws Exception {
    String out = getScriptArgs()[0];
    Memory mem=currentProgram.getMemory();
    long[][] ranges={{0L,0x160000L},{0x320000L,0x33ece0L}};
    int seeded=0;
    for(long[] r:ranges){ for(long o=r[0];o<r[1];o+=4){
      Address a=toAddr(o); int w=mem.getInt(a);
      boolean pro=((w&0xffff4000)==0xe92d4000)||(w==0xe1a0c00d);
      if(!pro) continue;
      if(getFunctionContaining(a)!=null) continue;
      if(getInstructionAt(a)==null) disassemble(a);
      if(getInstructionAt(a)!=null){ try{ if(createFunction(a,null)!=null) seeded++; }catch(Exception e){} }
    }}
    println("seeded "+seeded);
    analyzeChanges(currentProgram);
    FunctionManager fm=currentProgram.getFunctionManager();
    println("functions "+fm.getFunctionCount());
    PrintWriter asm=new PrintWriter(new BufferedWriter(new FileWriter(out+"/listing.txt")));
    InstructionIterator ii=currentProgram.getListing().getInstructions(true);
    while(ii.hasNext()){Instruction in=ii.next(); asm.println(in.getAddress()+"\t"+in.toString());}
    asm.close();
    DecompInterface di=new DecompInterface();
    di.setSimplificationStyle("decompile");
    di.openProgram(currentProgram);
    PrintWriter c=new PrintWriter(new BufferedWriter(new FileWriter(out+"/decomp.c")));
    FunctionIterator fi=fm.getFunctions(true); int n=0;
    while(fi.hasNext()&&!monitor.isCancelled()){
      Function f=fi.next();
      DecompileResults res=di.decompileFunction(f,60,monitor);
      c.println("//@@@ "+f.getEntryPoint()+" "+f.getBody().getNumAddresses());
      if(res!=null&&res.decompileCompleted()) c.println(res.getDecompiledFunction().getC());
      else c.println("// decompile failed");
      if(++n%500==0){println("dec "+n);c.flush();}
    }
    c.close(); di.dispose();
    println("done");
  }
}
