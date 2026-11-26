import {useState} from 'react';
import './quibar-assistant.css';

type Props={thinking:boolean;speaking:boolean;routeReady:boolean;selected:boolean;chatOpen:boolean;hidden:boolean;onOpen:()=>void};
export default function QuibarAssistant({thinking,speaking,routeReady,selected,chatOpen,hidden,onOpen}:Props){
 const [dismissed,setDismissed]=useState(false);
 const state=thinking?'thinking':speaking?'speaking':'idle';
 const message=thinking?'Estoy buscando información…':speaking?'Escucha mi guía del recorrido.':routeReady?'¡Tu ruta está lista!':selected?'¿Quieres saber más de este lugar?':chatOpen?'Estoy aquí para ayudarte.':'¡Hola! Soy Quíbar. ¿Qué descubrimos hoy?';
 if(hidden)return null;
 return <div className="quibar-float" data-state={state}>
  {!dismissed&&<div className="quibar-bubble"><button className="quibar-dismiss" aria-label="Ocultar saludo de Quíbar" onClick={()=>setDismissed(true)}>×</button><p role="status">{message}</p></div>}
  <button className="quibar-character" aria-label="Abrir asistente virtual Quíbar" onClick={()=>{setDismissed(false);onOpen();}}>
   <img className="quibar-motion" src="/quibar/hello.webp" alt=""/><img className="quibar-still" src="/quibar/idle.png" alt=""/><span>Pregúntame</span>
  </button>
 </div>;
}
